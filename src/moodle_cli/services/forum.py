"""Forum service."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from moodle_cli.services.base import BaseService, MoodleModel


class ForumRecord(MoodleModel):
    id: int
    course: int = 0
    name: str = ""
    type: str = ""
    intro: str = ""
    num_discussions: Annotated[int, Field(validation_alias="numdiscussions")] = 0


class DiscussionRecord(MoodleModel):
    id: int
    discussion: int = 0
    name: str = ""
    subject: str = ""
    message: str = ""
    user_id: Annotated[int, Field(validation_alias="userid")] = 0
    user_full_name: Annotated[str, Field(validation_alias="userfullname")] = ""
    time_modified: Annotated[int, Field(validation_alias="timemodified")] = 0
    # Activity signals returned by mod_forum_get_forum_discussions — previously
    # dropped, which is what blinded "who replied last / how many replies" and
    # broke the standing forum-debt ("ball with you") detection downstream.
    created: int = 0
    num_replies: Annotated[int, Field(validation_alias="numreplies")] = 0
    num_unread: Annotated[int, Field(validation_alias="numunread")] = 0
    user_modified: Annotated[int, Field(validation_alias="usermodified")] = 0
    user_modified_full_name: Annotated[str, Field(validation_alias="usermodifiedfullname")] = ""
    pinned: bool = False
    locked: bool = False


class Post(MoodleModel):
    id: int
    discussion_id: Annotated[int, Field(validation_alias="discussionid")] = 0
    # parentid is null on the root post; other id fields can be absent too.
    parent_id: Annotated[int | None, Field(validation_alias="parentid")] = None
    subject: str = ""
    message: str = ""
    time_created: Annotated[int, Field(validation_alias="timecreated")] = 0
    author: dict[str, object] = {}

    @property
    def author_name(self) -> str:
        a = self.author or {}
        return str(a.get("fullname") or a.get("name") or a.get("id") or "?")


class ForumService(BaseService):
    def list_forums(self, course_id: int) -> list[ForumRecord]:
        data = self.call("mod_forum_get_forums_by_courses", courseids=[course_id])
        return [ForumRecord.model_validate(f) for f in data]

    def get_discussions(self, forum_id: int) -> list[DiscussionRecord]:
        data = self.call("mod_forum_get_forum_discussions", forumid=forum_id)
        return [DiscussionRecord.model_validate(d) for d in data.get("discussions", [])]

    def get_posts(self, discussion_id: int) -> list[Post]:
        """Every post in a discussion (mod_forum_get_discussion_posts).

        Read-only: lists posts, does not log a view event (that would be
        mod_forum_view_forum_discussion, which is deliberately NOT allowlisted).
        """
        data = self.call("mod_forum_get_discussion_posts", discussionid=discussion_id)
        return [Post.model_validate(p) for p in data.get("posts", [])]

    def add_discussion(self, forum_id: int, subject: str, message: str) -> int:
        """Start a new discussion (write — only reachable via the full `moodle` CLI)."""
        data = self.call(
            "mod_forum_add_discussion",
            forumid=forum_id,
            subject=subject,
            message=message,
        )
        return int(data["discussionid"])

    def reply_to_post(self, post_id: int, subject: str, message: str) -> int:
        """Reply to an existing post in a discussion (write — only reachable via the
        full `moodle` CLI). ``post_id`` is the parent post being replied to, as listed
        by ``forum posts <discussion_id>``. Returns the new post's id."""
        data = self.call(
            "mod_forum_add_discussion_post",
            postid=post_id,
            subject=subject,
            message=message,
        )
        return int(data["postid"])
