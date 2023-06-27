from copy import deepcopy


class CeUpDeAtAdminMixser():

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            removed_at__isnull=True
        )

    # def get_fields(self, request, obj=None):
    #     fields = deepcopy(super().get_fields(request, obj=obj))
    #     if obj is None:
    #         for fiel_name in ['created_at', 'updated_at']:
    #             if fiel_name in fields:
    #                 fields.remove(fiel_name)
    #     if 'removed_at' in fields:
    #         fields.remove('removed_at')
    #     return fields

    def get_fieldsets(self, request, obj=None):
        fieldsets_new = []
        fieldsets = deepcopy(super().get_fieldsets(request, obj))
        for name, data in fieldsets:
            fields = list(deepcopy(data.get('fields', [])))
            if obj is None:
                for fiel_name in ['created_at', 'updated_at']:
                    if fiel_name in fields:
                        fields.remove(fiel_name)
            if 'removed_at' in fields:
                fields.remove('removed_at')
            if fields:
                data['fields'] = fields
                fieldsets_new.append((name, data))
        return fieldsets_new

    def get_readonly_fields(self, request, obj):
        fields = list(super().get_readonly_fields(request, obj=obj))
        if obj is not None:
            fields.extend(['created_at', 'updated_at'])
        return fields
