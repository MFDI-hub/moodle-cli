"""Cohort service."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from moodle_cli.services.base import BaseService, MoodleModel


class CohortRecord(MoodleModel):
    id: int
    name: str = ""
    id_number: Annotated[str, Field(validation_alias="idnumber")] = ""
    description: str = ""
    visible: bool = True


class CohortService(BaseService):
    def list_cohorts(self) -> list[CohortRecord]:
        data = self.call("core_cohort_get_cohorts")
        return [CohortRecord.model_validate(c) for c in data]

    def create_cohort(
        self,
        name: str,
        categorytype_type: str = "system",
        categorytype_value: str = "",
        id_number: str = "",
        description: str = "",
    ) -> CohortRecord:
        cohort_data: dict[str, Any] = {
            "categorytype": {"type": categorytype_type, "value": categorytype_value},
            "name": name,
            "idnumber": id_number,
            "description": description,
        }
        data = self.call("core_cohort_create_cohorts", cohorts=[cohort_data])
        return CohortRecord.model_validate(data[0])

    def delete_cohorts(self, cohort_ids: list[int]) -> None:
        self.call("core_cohort_delete_cohorts", cohortids=cohort_ids)

    def add_members(self, cohort_id: int, user_ids: list[int]) -> None:
        members = [{"cohortid": cohort_id, "userid": uid} for uid in user_ids]
        self.call("core_cohort_add_cohort_members", members=members)

    def remove_members(self, cohort_id: int, user_ids: list[int]) -> None:
        members = [{"cohortid": cohort_id, "userid": uid} for uid in user_ids]
        self.call("core_cohort_delete_cohort_members", members=members)
