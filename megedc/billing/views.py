from django.apps import apps
from django.core.cache import cache
from django.http import Http404
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response


class InvoiceDateRetriveAPIView(RetrieveAPIView):

    queryset = apps.get_model('billing.invoice').objects.all()

    def get(self, request, *args, **kwargs):
        if 'pk' not in self.kwargs:
            self.kwargs['pk'] = request.query_params.get('id')
        return super().get(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        preview = request.query_params.get('preview', 'false')
        is_preview = preview == 'true'
        if is_preview:
            data = cache.get('invoice_preview_%s' % (self.kwargs['pk']), None)
            if data is None:
                raise Http404
            data['is_preview'] = is_preview
            return Response(data)
        instance = self.get_object()
        instance.data['id_preview'] = is_preview
        return Response(instance.data)
