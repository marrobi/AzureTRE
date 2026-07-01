from db.repositories.resources import ResourceRepository


class ResourceMigration(ResourceRepository):
    @classmethod
    async def create(cls):
        cls = ResourceMigration()
        resource_repo = await super().create()
        cls._container = resource_repo._container
        return cls

    async def add_unique_identifier_suffix_field(self) -> int:
        """Add a unique_identifier_suffix property to workspaces created before the field existed.

        The value used is the last 4 characters of the workspace id, which is what was previously
        used to build the workspace-scoped (base and airlock) storage account names. This preserves
        the existing storage account names for already-deployed workspaces (see #2893, #3666).
        Only workspaces are backfilled - workspace services and user resources are out of scope.
        """
        num_updated = 0
        for resource in await self.query("SELECT * from c WHERE c.resourceType = 'workspace' AND NOT IS_DEFINED(c.properties.unique_identifier_suffix)"):
            if "properties" not in resource:
                resource["properties"] = {}
            resource["properties"]["unique_identifier_suffix"] = resource["id"][-4:]
            await self.update_item_dict(resource)
            num_updated = num_updated + 1

        return num_updated
