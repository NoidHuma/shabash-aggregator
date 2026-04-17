NEW_POSTS_STREAM = "new_posts"

CANDIDATE_POSTS_STREAM = "candidate_posts"

FILTERED_POSTS_STREAM = "filtered_posts"

PREPARED_POSTS_STREAM = "prepared_posts"


# Consumer groups (по одной на этап-читатель потока).
COARSE_FILTER_GROUP = "coarse_filter"
ML_FILTER_GROUP = "ml_filter"
ATTRIBUTE_EXTRACTOR_GROUP = "attribute_extractor"

# Публикаторы: каждый читает prepared_posts СВОЕЙ группой, чтобы получать
# каждую заявку независимо (а не делить их между собой).
VK_GROUP_PUBLISHER_GROUP = "vk_group_publisher"
TG_CHANNEL_PUBLISHER_GROUP = "tg_channel_publisher"
VK_BOT_DISPATCHER_GROUP = "vk_bot_dispatcher"
TG_BOT_DISPATCHER_GROUP = "tg_bot_dispatcher"