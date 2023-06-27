import uuid
from django.apps import apps
from django.core.cache import cache


def invoice_uuid_generator(*args, **kwargs):
    return str(uuid.uuid4())


invoice_uuid_generator.id = 'UUID'
invoice_uuid_generator.name = 'UUID Generator'


class InvoiceAutoIncrementIdGenerator:

    id = 'AUTOINSCREMENT'
    name = 'Auto Increment'

    def __call__(self, *args, **kwargs):
        client = kwargs.get('client')
        if client is None:
            raise KeyError('client parm not found for %s' % self.name)
        generator_kwargs = client.invoiceidgenerator_kwargs
        fill_length = generator_kwargs.get('length', 10)
        first_value = generator_kwargs.get('first_value', 0)
        increment = generator_kwargs.get('increment', 1)
        tax_id = (
            client.invoicetaxid
            if client.invoicetaxid is not None else
            client.id
        )
        cache_base_key = 'IAIIG:%s' % (tax_id)
        with cache.lock('%s:%s' % (cache_base_key, 'lock')):
            cache_cv = '%s:%s' % (cache_base_key, 'current')
            current_id = cache.get(cache_cv, None)
            if current_id is None:
                q_client = None
                if isinstance(client, apps.get_model('general.Customer')):
                    q_client = client.client
                elif isinstance(client, apps.get_model('general.Client')):
                    q_client = client
                qs_filter_kwargs = {
                    'customer__client': q_client,
                    'data__generator_id': self.id,
                }
                if client.invoicetaxid is not None:
                    qs_filter_kwargs[
                        'data__header__tax_id'
                    ] = client.invoicetaxid
                else:
                    qs_filter_kwargs[
                        'data__header__id'
                    ] = client.invoicetaxid
                invoice_manager = apps.get_model('billing.Invoice').objects
                queryset = invoice_manager.filter(**qs_filter_kwargs)
                current_id = first_value
                for row in queryset.values('invoice_id').iterator():
                    val = current_id
                    try:
                        val = int(row['invoice_id'])
                    except ValueError:
                        continue
                    if val > current_id:
                        current_id = val
            next_val = current_id + increment
            cache.set(cache_cv, next_val, timeout=None)
            return str(next_val).zfill(fill_length)


GENERATORS_HANDLERS = [
    invoice_uuid_generator,
    InvoiceAutoIncrementIdGenerator()
]


class Generators:

    @classmethod
    def choices(cls):
        choices = []
        for generator in GENERATORS_HANDLERS:
            if hasattr(generator, 'name') and hasattr(generator, 'id'):
                choices.append(
                    (getattr(generator, 'id'), getattr(generator, 'name'))
                )
        return choices

    @classmethod
    def get(cls, ganerator_id):
        for generator in GENERATORS_HANDLERS:
            if getattr(generator, 'id') == ganerator_id:
                return generator
        raise NotImplementedError(
            'Generanot id "%s" not implemented' % ganerator_id
        )

    default_generator_id = 'UUID'
