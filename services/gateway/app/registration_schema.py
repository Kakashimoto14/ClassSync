"""Academic-only extraction/review contracts. A document is never identity authority."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PrivateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*")
    @classmethod
    def no_controls(cls, value):
        if isinstance(value, str) and any(ord(char) < 32 for char in value):
            raise ValueError("Control characters are not permitted")
        return value


class ReviewedCourse(PrivateInput):
    code: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=240)
    section: str = Field(default="", max_length=80)


class ReviewedAcademicFields(PrivateInput):
    academic_year: str = Field(pattern=r"^\d{4}-\d{4}$")
    semester: Literal["first", "second"]
    program: str = Field(default="", max_length=160)
    year_level: int | None = Field(default=None, strict=True, ge=1, le=20)
    courses: list[ReviewedCourse] = Field(min_length=1, max_length=60)

    @model_validator(mode="after")
    def year_range(self):
        first, second = map(int, self.academic_year.split("-"))
        if second != first + 1:
            raise ValueError("Academic year must contain consecutive years")
        return self


class RegistrationReview(ReviewedAcademicFields):
    student_identifier: str = Field(min_length=8, max_length=8, pattern=r"^[0-9]{2}-[0-9]{5}$")


def review_openapi_schema():
    schema = RegistrationReview.model_json_schema()
    definitions = schema.pop("$defs", {})

    def inline(value):
        if isinstance(value, dict):
            if "$ref" in value:
                return inline(definitions[value["$ref"].split("/")[-1]])
            return {key: inline(item) for key, item in value.items()}
        if isinstance(value, list):
            return [inline(item) for item in value]
        return value

    return inline(schema)
