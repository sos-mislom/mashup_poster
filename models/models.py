from abstract_models.abstract_models import *
from typing import Optional

class Post(DataBaseObject):
    post_id: Optional[int]

    TABLE_NAME = 'posts'
