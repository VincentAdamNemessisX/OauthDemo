# --- 辅助函数 ---
from typing import Optional

from model.mock_model import User


def get_user_by_github_id(db, github_id: int) -> Optional[User]:
    """根据 GitHub ID 从模拟数据库获取用户"""
    # 实际应用中这里应该是数据库查询
    for user in db.values():
        if user.github_id == github_id:
            return user
    return None


def add_or_update_user(db, user_data: dict) -> User:
    """根据从 GitHub 获取的数据添加或更新用户"""
    github_id = user_data.get("id")
    if not github_id:
        raise ValueError("GitHub user data must contain 'id'")

    existing_user = get_user_by_github_id(db, github_id)

    user_info = User(
        username=user_data.get("login"),
        github_id=github_id,
        name=user_data.get("name"),
        email=user_data.get("email"),
        avatar_url=user_data.get("avatar_url"),
        disabled=existing_user.disabled if existing_user else False  # 保留之前的禁用状态
    )

    # 使用 github_id 作为 key 存储用户，更可靠
    db[github_id] = user_info
    return user_info
