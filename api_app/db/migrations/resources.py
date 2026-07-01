from db.repositories.resources import ResourceRepository


class ResourceMigration(ResourceRepository):
    @classmethod
    async def create(cls):
        cls = ResourceMigration()
        resource_repo = await super().create()
        cls._container = resource_repo._container
        return cls

    async def add_unique_identifier_suffix_field(self) -> int:
        """Add a unique_identifier_suffix property to resources created before the field existed.

        The value used is the last 4 characters of the resource id, which is what was previously
        used to build globally-unique resource names (e.g. storage accounts). This preserves the
        existing resource names for already-deployed resources (see #2893, #3243, #3666).
        """
        num_updated = 0
        for resource in await self.query("SELECT * from c WHERE NOT IS_DEFINED(c.properties.unique_identifier_suffix)"):
            if "properties" not in resource:
                resource["properties"] = {}
            resource["properties"]["unique_identifier_suffix"] = resource["id"][-4:]
            await self.update_item_dict(resource)
            num_updated = num_updated + 1

        return num_updated
