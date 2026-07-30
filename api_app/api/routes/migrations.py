from fastapi import APIRouter, Depends, HTTPException, status
from api.helpers import get_repository
from db.migrations.resources import ResourceMigration
from services.authentication import get_current_admin_user
from resources import strings
from models.schemas.migrations import MigrationOutList, Migration
from services.logging import logger

migrations_core_router = APIRouter(dependencies=[Depends(get_current_admin_user)])


@migrations_core_router.post("/migrations",
                             status_code=status.HTTP_202_ACCEPTED,
                             name=strings.API_MIGRATE_DATABASE,
                             response_model=MigrationOutList,
                             dependencies=[Depends(get_current_admin_user)])
async def migrate_database(resource_migration=Depends(get_repository(ResourceMigration))):
    try:
        migrations = list()

        # Examples of additional migrations can be found in this file:
        # https://github.com/microsoft/AzureTRE/blob/v0.22.0/api_app/api/routes/migrations.py#L32-L84
        # and this folder:
        # https://github.com/microsoft/AzureTRE/tree/v0.22.0/api_app/db/migrations

        logger.info("Running migration add_unique_identifier_suffix_field (#2893)")
        num_rows = await resource_migration.add_unique_identifier_suffix_field()
        migrations.append(Migration(issueNumber="2893", status=f'Updated {num_rows} resource objects'))

        return MigrationOutList(migrations=migrations)
    except Exception as e:
        logger.exception("Failed to migrate database")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
