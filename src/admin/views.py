from slugify import slugify
from sqladmin import action
from sqladmin import ModelView
from sqlalchemy import update
from starlette.requests import Request
from starlette.responses import RedirectResponse
from markupsafe import Markup

from src.models.animal_type import AnimalType
from src.models.business import Business
from src.models.business_category import BusinessCategory
from src.models.business_hours import BusinessHours
from src.models.enums import BusinessStatus
from src.models.service import Service
from src.models.user import User

def _format_status(status) -> Markup:
    """Render BusinessStatus as a colored badge."""
    colors = {
        "pending": "#f59e0b",   # amber
        "approved": "#10b981",  # green
        "rejected": "#ef4444",  # red
    }
    value = status.value if hasattr(status, "value") else str(status)
    color = colors.get(value, "#6b7280")
    return Markup(
        f'<span style="background-color: {color}; color: white; '
        f'padding: 2px 8px; border-radius: 4px; font-size: 0.85em; '
        f'text-transform: uppercase;">{value}</span>'
    )


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
    can_delete = False

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

class BusinessCategoryAdmin(ModelView, model=BusinessCategory):
    """Admin view for managing business categories (vet_clinic, grooming, etc)."""
    name = "Business Category"
    name_plural = "Business Categories"
    icon = "fa-solid fa-tags"

    can_delete = False
    can_create = False

    column_list = [
        BusinessCategory.id,
        BusinessCategory.slug,
        BusinessCategory.name,
        BusinessCategory.icon_url,
        BusinessCategory.sort_order,
        BusinessCategory.is_active,
    ]
    column_default_sort = [(BusinessCategory.sort_order, False)]
    column_searchable_list = [BusinessCategory.slug, BusinessCategory.name]
    column_sortable_list = [
        BusinessCategory.id,
        BusinessCategory.slug,
        BusinessCategory.name,
        BusinessCategory.sort_order,
        BusinessCategory.is_active,
    ]

    form_columns = [
        BusinessCategory.name,
        BusinessCategory.icon_url,
        BusinessCategory.sort_order,
        BusinessCategory.is_active,
    ]

    column_details_list = [
        BusinessCategory.id,
        BusinessCategory.slug,
        BusinessCategory.name,
        BusinessCategory.icon_url,
        BusinessCategory.sort_order,
        BusinessCategory.is_active,
        BusinessCategory.created_at,
        BusinessCategory.updated_at,
    ]


class ServiceAdmin(ModelView, model=Service):
    """Admin view for managing services within categories."""
    name = "Service"
    name_plural = "Services"
    icon = "fa-solid fa-list-check"

    can_delete = False

    column_list = [
        Service.id,
        Service.slug,
        Service.name,
        "category.name",  # Show category name instead of category_id
        Service.sort_order,
        Service.is_active,
    ]
    column_labels = {"category.name": "Category"}
    column_default_sort = [
        (Service.category_id, False),
        (Service.sort_order, False),
    ]
    column_searchable_list = [Service.slug, Service.name]
    column_sortable_list = [
        Service.id,
        Service.slug,
        Service.name,
        Service.sort_order,
        Service.is_active,
    ]

    # Form: category will render as a dropdown of all BusinessCategory records
    form_columns = [
        Service.name,
        Service.category,
        Service.sort_order,
        Service.is_active,
    ]

    column_details_list = [
        Service.id,
        Service.slug,
        Service.name,
        Service.category,
        Service.sort_order,
        Service.is_active,
        Service.created_at,
        Service.updated_at,
    ]

    async def on_model_change(self, data, model, is_created, request):
            """Auto-generate slug from name when creating a new service."""
            if is_created and data.get("name") and not model.slug:
                model.slug = slugify(data["name"], max_length=200)

class BusinessAdmin(ModelView, model=Business):
    """Admin view for managing businesses, including moderation."""
    name = "Business"
    name_plural = "Businesses"
    icon = "fa-solid fa-store"

    # Admin doesn't create businesses — users propose them via POST /businesses.
    # Admin DOES delete (e.g., spam, offensive content).
    can_create = False

    column_list = [
        Business.id,
        Business.name,
        Business.status,
        "category.name",
        Business.city,
        "owner.email",
        Business.accepts_emergencies,
        Business.created_at,
    ]
    column_labels = {
        "category.name": "Category",
        "owner.email": "Owner",
    }
    column_default_sort = [(Business.created_at, True)]  # newest first
    # Render status as a colored badge in list and details views
    column_formatters = {
        Business.status: lambda obj, _: _format_status(obj.status),
    }
    column_formatters_detail = {
        Business.status: lambda obj, _: _format_status(obj.status),
    }
    column_searchable_list = [Business.name, Business.slug, Business.address]
    column_sortable_list = [
        Business.id,
        Business.name,
        Business.status,
        Business.city,
        Business.created_at,
    ]

    # Edit form — owner and slug are intentionally read-only.
    # owner: changing it would be a security issue.
    # slug: used in URLs, regenerate via separate flow if needed.
    form_columns = [
        Business.name,
        Business.description,
        Business.category,
        Business.status,
        Business.address,
        Business.city,
        Business.latitude,
        Business.longitude,
        Business.phone,
        Business.website,
        Business.email,
        Business.accepts_emergencies,
        Business.emergency_24_7,
        Business.cover_image_url,
        Business.animal_types,
        Business.services,
    ]

    column_details_list = [
        Business.id,
        Business.name,
        Business.slug,
        Business.description,
        Business.status,
        Business.category,
        Business.owner,
        Business.address,
        Business.city,
        Business.latitude,
        Business.longitude,
        Business.phone,
        Business.website,
        Business.email,
        Business.accepts_emergencies,
        Business.emergency_24_7,
        Business.cover_image_url,
        Business.animal_types,
        Business.services,
        Business.hours,
        Business.created_at,
        Business.updated_at,
    ]

    @action(
        name="approve_businesses",
        label="Approve",
        confirmation_message="Approve selected businesses?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def approve_businesses(self, request: Request) -> RedirectResponse:
        """Mark selected businesses as approved."""
        pks = request.query_params.get("pks", "").split(",")
        pks = [int(pk) for pk in pks if pk]

        if pks:
            session = self.session_maker()
            async with session as db:
                await db.execute(
                    update(Business)
                    .where(Business.id.in_(pks))
                    .values(status=BusinessStatus.APPROVED)
                )
                await db.commit()

        referer = request.headers.get("Referer", request.url_for("admin:list", identity="business"))
        return RedirectResponse(url=str(referer), status_code=302)

    @action(
        name="reject_businesses",
        label="Reject",
        confirmation_message="Reject selected businesses?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def reject_businesses(self, request: Request) -> RedirectResponse:
        """Mark selected businesses as rejected."""
        pks = request.query_params.get("pks", "").split(",")
        pks = [int(pk) for pk in pks if pk]

        if pks:
            session = self.session_maker()
            async with session as db:
                await db.execute(
                    update(Business)
                    .where(Business.id.in_(pks))
                    .values(status=BusinessStatus.REJECTED)
                )
                await db.commit()

        referer = request.headers.get("Referer", request.url_for("admin:list", identity="business"))
        return RedirectResponse(url=str(referer), status_code=302)
    
