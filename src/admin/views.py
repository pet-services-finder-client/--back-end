from sqladmin import ModelView

from src.models.user import User


class UserAdmin(ModelView, model=User):
    """Admin view for managing users."""

    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"

    # What columns to show in the list view
    column_list = [
        User.id,
        User.email,
        User.full_name,
        User.is_active,
        User.is_verified,
        User.is_admin,
        User.created_at,
    ]

    # Default sorting in the list view
    column_default_sort = [(User.created_at, True)]  # True = descending

    # Searchable columns
    column_searchable_list = [User.email, User.full_name]

    # Sidebar filters
    column_sortable_list = [
        User.id,
        User.email,
        User.is_active,
        User.is_admin,
        User.created_at,
    ]

    # Fields shown when creating a new user — disabled because we don't want
    # admins creating users directly (they should self-register)
    can_create = False

    # Fields shown when editing an existing user
    form_columns = [
        User.full_name,
        User.is_active,
        User.is_verified,
        User.is_admin,
    ]

    # Show full email in details view
    column_details_list = [
        User.id,
        User.email,
        User.full_name,
        User.is_active,
        User.is_verified,
        User.is_admin,
        User.created_at,
        User.updated_at,
    ]

    # Don't allow deletion through admin — use is_active=False instead
    can_delete = False


from src.models.animal_type import AnimalType


class AnimalTypeAdmin(ModelView, model=AnimalType):
    """Admin view for managing animal types."""

    name = "Animal Type"
    name_plural = "Animal Types"
    icon = "fa-solid fa-paw"

    column_list = [
        AnimalType.id,
        AnimalType.slug,
        AnimalType.name,
        AnimalType.icon_url,
        AnimalType.sort_order,
        AnimalType.is_active,
    ]

    column_default_sort = [(AnimalType.sort_order, False)]  # asc

    column_searchable_list = [AnimalType.slug, AnimalType.name]

    column_sortable_list = [
        AnimalType.id,
        AnimalType.slug,
        AnimalType.name,
        AnimalType.sort_order,
        AnimalType.is_active,
    ]

    # Admin can fully manage animal types — no security concerns here
    form_columns = [
        AnimalType.slug,
        AnimalType.name,
        AnimalType.icon_url,
        AnimalType.sort_order,
        AnimalType.is_active,
    ]

    column_details_list = [
        AnimalType.id,
        AnimalType.slug,
        AnimalType.name,
        AnimalType.icon_url,
        AnimalType.sort_order,
        AnimalType.is_active,
        AnimalType.created_at,
        AnimalType.updated_at,
    ]
