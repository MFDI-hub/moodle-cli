"""HTML fixtures for session page readers."""

from __future__ import annotations

from moodle_cli.client.pages import (
    instance_from_html,
    parse_assign_view,
    parse_badges,
    parse_categories,
    parse_choice_results,
    parse_cohorts,
    parse_completion,
    parse_conversations,
    parse_database,
    parse_enrol_methods,
    parse_files,
    parse_forum_discussions,
    parse_forum_posts,
    parse_glossary,
    parse_grade_report,
    parse_groups,
    parse_lesson,
    parse_messages,
    parse_notes,
    parse_participants,
    parse_quiz_review,
    parse_quiz_view,
    parse_wiki_page,
    parse_wiki_pages,
    parse_workshop,
    section_summary,
)


def test_section_table_names_files_from_topic() -> None:
    summary, links, rows = section_summary(
        """
        <div class="summarytext">
          <p>Late lectures may change.</p>
          <table>
            <tr><th>Week</th><th>Date</th><th>Topic</th><th>Slides</th><th>Handouts</th></tr>
            <tr>
              <td rowspan="2">1</td>
              <td>22 Sept</td>
              <td>Self reading</td>
              <td><a href="https://www.rsipvision.com/ComputerVisionNews-2026July/">Reading docs</a></td>
              <td></td>
            </tr>
            <tr>
              <td>2 Oct</td>
              <td>Lecture 1 The Eye</td>
              <td><a href="https://sotonac.sharepoint.com/:b:/t/x/abc">PDF</a></td>
              <td><a href="https://en.wikipedia.org/wiki/Nyquist-Shannon_sampling_theorem">link</a></td>
            </tr>
          </table>
        </div>
        """,
        "https://moodle.example.com",
    )
    assert "Late lectures may change." in summary
    assert "Week" not in summary
    assert rows[0]["Week"] == "1"
    assert rows[0]["Topic"] == "Self reading"
    assert rows[1]["Week"] == "1"
    assert rows[1]["Topic"] == "Lecture 1 The Eye"
    names = [link["name"] for link in links]
    assert "Self reading — Reading docs" in names
    assert "Lecture 1 The Eye (Slides)" in names
    assert any("Nyquist" in name for name in names)


def test_grade_report_rows() -> None:
    items = parse_grade_report(
        """
        <table class="user-grade">
          <tr><th class="column-itemname">Grade item</th>
              <td class="column-grade">Grade</td></tr>
          <tr><th class="column-itemname">Essay</th>
              <td class="column-grade">12.00</td>
              <td class="column-range">0-20</td>
              <td class="column-feedback">ok</td></tr>
        </table>
        """
    )
    assert items[0]["itemname"] == "Essay"
    assert items[0]["grade"] == "12.00"
    assert items[0]["grademax"] == 20.0


def test_assign_view_status_and_instance() -> None:
    html = """
    <h1>Coursework 1</h1>
    <input type="hidden" name="assignid" value="55">
    <div id="region-main">Submitted for grading. Grade: 90.00
    <time datetime="2026-11-17T12:00:00+00:00">due</time></div>
    """
    assert instance_from_html(html, "assign", 10) == 55
    data = parse_assign_view(html, 10, 831)
    assert data["id"] == 55
    assert data["status"]["status"] == "submitted"
    assert data["gradevalue"] == "90.00"
    assert data["duedate"] > 0


def test_forum_discussions_and_posts() -> None:
    discussions = parse_forum_discussions(
        """
        <table>
          <tr>
            <td><a href="/mod/forum/discuss.php?d=99">Welcome</a></td>
            <td><a href="/user/view.php?id=2">Ada</a></td>
            <td>4</td>
          </tr>
        </table>
        """,
        forum_id=44,
    )
    assert discussions[0]["discussion"] == 99
    assert discussions[0]["userfullname"] == "Ada"
    assert discussions[0]["numreplies"] == 4
    posts = parse_forum_posts(
        """
        <article class="forumpost" id="p7">
          <h3>Welcome</h3>
          <a href="/user/view.php?id=2">Ada</a>
          <div class="post-message">Hello class</div>
        </article>
        """,
        99,
    )
    assert posts[0]["id"] == 7
    assert posts[0]["author"]["fullname"] == "Ada"
    assert "Hello class" in posts[0]["message"]


def test_quiz_view_and_review() -> None:
    view = parse_quiz_view(
        """
        <h1>Quiz 1</h1>
        Highest grade: 8.5
        <table class="quizattemptsummary">
          <tr><td>1</td><td>Finished</td><td>8.50</td>
              <td><a href="/mod/quiz/review.php?attempt=3">Review</a></td></tr>
        </table>
        """,
        quiz_id=77,
    )
    assert view["hasgrade"] is True
    assert view["grade"] == 8.5
    assert view["attempts"][0]["id"] == 3
    review = parse_quiz_review(
        """
        Grade 8.50
        <div class="que">
          <div class="qtext">What is vision?</div>
          <div class="grade">Mark 1.00 out of 1.00</div>
          <div class="state">Correct</div>
        </div>
        """,
        3,
    )
    assert review["questions"][0]["html"] == "What is vision?"
    assert review["questions"][0]["status"] == "Correct"


def test_participants_groups_categories() -> None:
    people = parse_participants(
        """
        <table id="participants">
          <tr>
            <td><a href="/user/view.php?id=7&amp;course=831">Mehmet Icen</a></td>
            <td>mf@example.com</td>
            <td>Student</td>
          </tr>
        </table>
        """,
        831,
    )
    assert people[0]["id"] == 7
    assert people[0]["email"] == "mf@example.com"
    groups = parse_groups(
        '<select id="groups"><option value="0">Choose</option>'
        '<option value="5">Lab A (2)</option></select>',
        831,
    )
    assert groups[0] == {
        "id": 5,
        "courseid": 831,
        "name": "Lab A",
        "description": "",
        "descriptionformat": 1,
    }
    cats = parse_categories('<a href="/course/index.php?categoryid=57">Computer Science</a>')
    assert cats[0]["name"] == "Computer Science"


def test_completion_messages_badges_files() -> None:
    statuses = parse_completion(
        '<tr><td><a href="/mod/assign/view.php?id=10">CW1</a></td><td>Completed</td></tr>'
    )
    assert statuses[0]["cmid"] == 10
    assert statuses[0]["state"] == 1
    messages = parse_messages(
        '<div data-message-id="8"><a href="/user/view.php?id=2">Ada</a> Hi</div>'
    )
    assert messages[0]["id"] == 8
    conversations = parse_conversations('<a data-conversation-id="3">Ada</a>')
    assert conversations[0]["id"] == 3
    badges = parse_badges('<div class="badge"><h3 class="badge-name">Starter</h3></div>')
    assert badges[0]["name"] == "Starter"
    files = parse_files(
        '<a href="/pluginfile.php/9/user/private/notes.pdf">notes.pdf</a>',
        "https://moodle.example.com",
    )
    assert files[0]["filename"] == "notes.pdf"


def test_remaining_activity_readers() -> None:
    assert parse_workshop('<a href="/mod/workshop/submission.php?sid=4">Draft</a>')[0]["id"] == 4
    assert (
        parse_glossary(
            '<div class="glossarypost"><div class="concept">HTTP</div>'
            '<div class="definition">Hypertext</div></div>'
        )[0]["concept"]
        == "HTTP"
    )
    assert parse_database('<a href="/mod/data/view.php?rid=6">Row</a>')[0]["id"] == 6
    pages = parse_wiki_pages('<a href="/mod/wiki/view.php?pageid=2">Home</a>')
    assert pages[0]["title"] == "Home"
    page = parse_wiki_page(
        '<h1>Home</h1><div id="region-main"><div class="wiki_content">Body</div></div>',
        2,
    )
    assert page["cachedcontent"] == "Body"
    lesson = parse_lesson('<a href="/mod/lesson/view.php?id=1&pageid=8">Intro</a>')
    assert lesson[0]["page"]["id"] == 8
    notes = parse_notes(
        '<div class="note"><a href="/user/view.php?id=7">Mehmet</a> Keep going</div>',
        831,
    )
    assert "Keep going" in notes[0]["content"]
    options = parse_choice_results(
        "<table><tr><th>Option</th><th>Count</th></tr><tr><td>Yes</td><td>4</td></tr></table>"
    )
    assert options[0]["text"] == "Yes"
    cohorts = parse_cohorts('<a href="/cohort/view.php?id=3">2026 CS</a>')
    assert cohorts[0]["name"] == "2026 CS"
    methods = parse_enrol_methods(
        "<table><tr><th>Name</th><th>Status</th></tr><tr><td>Manual</td><td>Open</td></tr></table>",
        831,
    )
    assert methods[0]["name"] == "Manual"
