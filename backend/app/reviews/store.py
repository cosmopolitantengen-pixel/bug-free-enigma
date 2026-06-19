from __future__ import annotations

from app.core.models import TaskReview


class ReviewStore:
    def __init__(self, reviews: list[TaskReview] | None = None) -> None:
        self._reviews: dict[str, TaskReview] = {review.review_id: review for review in reviews or []}

    def record(self, review: TaskReview) -> TaskReview:
        self._reviews[review.review_id] = review
        return review

    def get(self, review_id: str) -> TaskReview:
        return self._reviews[review_id]

    def list(self, task_id: str | None = None, reviewer_agent: str | None = None) -> list[TaskReview]:
        reviews = list(self._reviews.values())
        if task_id is not None:
            reviews = [review for review in reviews if review.task_id == task_id]
        if reviewer_agent is not None:
            reviews = [review for review in reviews if review.reviewer_agent == reviewer_agent]
        return reviews
