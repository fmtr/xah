from xah.toolsets.base.tool import Tool
class CollectionValidator(Tool):
    """Validate collection access shared by knowledgebase read tools."""

    collection_id: str

    async def validate(self):
        collection = self.toolset.collection_for(self.collection_id)
        if collection.APPROVAL:
            self.validation.approval = True
            self.validation.messages.approval.append(
                f"The {collection.name} collection is protected and requires user approval."
            )
