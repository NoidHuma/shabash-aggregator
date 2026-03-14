from enum import Enum


class PostStatus(Enum):

    NEW = "new"

    COARSE_FILTER_PASSED = "coarse_filter_passed"
    COARSE_FILTER_REJECTED = "coarse_filter_rejected"

    ML_FILTER_PASSED = "ml_filter_passed"
    ML_FILTER_REJECTED = "ml_filter_rejected"

    ATTRIBUTES_EXTRACTED = "attributes_extracted"