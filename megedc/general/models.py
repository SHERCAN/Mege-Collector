import uuid
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from megedc.billing.invoice_id import Generators
from megedc.billing.invoice_makers import InvoiceMakers
from timezone_field import TimeZoneField


class Currency(models.Model):

    name = models.CharField(
        max_length=128,
        help_text='Currency name'
    )

    desc = models.TextField(
        null=True,
        blank=True,
        help_text='Currency description'
    )

    synbol = models.CharField(
        max_length=10,
        help_text='Currency synbol'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return '%s %s' % (self.synbol, self.name)


class Client(models.Model):

    name = models.CharField(
        max_length=128,
        help_text='Client name'
    )

    desc = models.TextField(
        null=True,
        blank=True,
        help_text='Client description'
    )

    time_zone = TimeZoneField(
        default='UTC',
        help_text='Client timezone'
    )

    invoice_makers_allowed = ArrayField(
        models.CharField(
            max_length=20,
            choices=InvoiceMakers.choices()
        ),
        default=list,
        null=True,
        blank=True,
    )

    invoice_maker = models.CharField(
        max_length=20,
        default=InvoiceMakers.default
    )

    invoice_maker_kwargs = models.JSONField(
        default=dict,
        null=True,
        blank=True
    )

    invoice_id_generator = models.CharField(
        max_length=20,
        help_text='Invoice id generator',
        choices=Generators.choices(),
        default=Generators.default_generator_id
    )

    invoice_id_generator_kwargs = models.JSONField(
        default=dict,
        null=True,
        blank=True
    )

    tax_id = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    invoice_tax = models.FloatField(
        help_text="Tax % on invoice",
        default=0.0,
        validators=[MaxValueValidator(100.0), MinValueValidator(0.0)]
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    currency_model = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name='clients',
        verbose_name='currency'
    )

    @property
    def timezone(self):
        return self.time_zone

    @property
    def invoicetax(self):
        return self.invoice_tax

    @property
    def invoicetaxid(self):
        return self.tax_id

    @property
    def invoiceidgenerator(self):
        return Generators.get(self.invoice_id_generator)

    @property
    def invoicemaker(self):
        return InvoiceMakers.get(self.invoice_maker)

    @property
    def next_invoice_id(self):
        return self.invoiceidgenerator(client=self)

    def __str__(self):
        return self.name


class MegeUser(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='megeuser'
    )

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='user',
    )


class Project(models.Model):

    uuid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4
    )

    name = models.CharField(
        max_length=128,
        help_text='Project name'
    )

    desc = models.TextField(
        null=True,
        blank=True,
        help_text='Project description'
    )

    time_zone = TimeZoneField(
        null=True,
        blank=True,
        help_text='Project timezone'
    )

    enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    removed_at = models.DateTimeField(
        null=True,
    )

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='projects',
    )

    currency_model = models.ForeignKey(
        Currency,
        null=True,
        on_delete=models.CASCADE,
        related_name='projects',
        verbose_name='currency'
    )

    @property
    def timezone(self):
        if not self.time_zone:
            return self.client.timezone
        return self.time_zone

    def __str__(self):
        return self.name


class Customer(models.Model):

    name = models.CharField(
        max_length=128,
        help_text='Customer name'
    )

    legal_id = models.CharField(
        max_length=128,
        help_text='Legal identifier',
        null=True,
        blank=True
    )

    desc = models.TextField(
        null=True,
        blank=True,
        help_text='Customer description'
    )

    addess = models.TextField(
        null=True,
        blank=True,
        help_text='Customer address',
        verbose_name='Address'
    )

    phones = ArrayField(
        models.CharField(max_length=128, blank=True, null=True, default=' '),
        default=list,
        null=True,
        blank=True,
        help_text='Customer phones',
    )

    emails = ArrayField(
        models.EmailField(max_length=128, blank=True, null=True, default=' '),
        default=list,
        null=True,
        blank=True,
        help_text='Customer EMails',
    )

    invoice_maker = models.CharField(
        max_length=20,
        null=True,
        blank=True
    )

    invoice_maker_kwargs = models.JSONField(
        null=True,
        blank=True
    )

    invoice_id_generator = models.CharField(
        max_length=20,
        help_text='Invoice id generator',
        choices=Generators.choices(),
        null=True,
        blank=True
    )

    invoice_id_generator_kwargs = models.JSONField(
        null=True,
        blank=True
    )

    tax_id = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    invoice_tax = models.FloatField(
        help_text="Tax % on invoice",
        null=True,
        blank=True,
    )

    is_invoice_header = models.BooleanField(default=False)

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    removed_at = models.DateTimeField(
        null=True
    )

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='curtomers',
    )

    @property
    def invoicetax(self):
        if self.invoice_tax is None:
            return self.client.invoicetax
        return self.invoice_tax

    @property
    def invoicetaxid(self):
        if self.tax_id is None:
            return self.client.invoicetaxid
        return self.tax_id

    @property
    def invoicemaker(self):
        if self.invoice_maker is None:
            return self.client.invoicemaker
        return Generators.get(self.invoice_maker)

    @property
    def invoicemaker_kwargs(self):
        if self.invoice_maker_kwargs is None:
            return self.client.invoice_maker_kwargs
        return self.invoice_maker_kwargs

    @property
    def invoiceidgenerator(self):
        if self.invoice_id_generator is None:
            return self.client.invoiceidgenerator
        return Generators.get(self.invoice_id_generator)

    @property
    def invoiceidgenerator_kwargs(self):
        if self.invoice_id_generator_kwargs is None:
            return self.client.invoice_id_generator_kwargs
        return self.invoice_id_generator_kwargs

    @property
    def next_invoice_id(self):
        return self.invoiceidgenerator(client=self)

    def make_invoice(self, **kwargs):
        return self.invoicemaker(self, **kwargs)

    def __str__(self):
        return self.name


class Local(models.Model):

    name = models.CharField(
        max_length=128,
        help_text='Local name'
    )

    desc = models.TextField(
        null=True,
        blank=True,
        help_text='Local description'
    )

    extra = models.JSONField(
        default=dict,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    removed_at = models.DateTimeField(
        null=True
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='local',
    )

    def __str__(self):
        return self.name


class Rental(models.Model):

    start_at = models.DateTimeField()

    end_at = models.DateTimeField(null=True)

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    removed_at = models.DateTimeField(
        null=True
    )

    local = models.ForeignKey(
        Local,
        on_delete=models.CASCADE,
        related_name='rentals',
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='rentals',
    )

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)
        if self.end_at is not None and self.end_at <= self.start_at:
            raise ValidationError(
                'Invalid end_date, a higher value is necessary'
            )

    def validate_unique(self, exclude=None):
        super().validate_unique(exclude)
        manager = self.__class__.objects
        queryset = manager.filter(
            removed_at__isnull=True,
            local=self.local,
        ).filter(
            models.Q(end_at__isnull=True)
            | models.Q(end_at__gte=self.start_at),
        )
        if self.pk is not None:
            queryset = queryset.exclude(pk=self.pk)
        local_already_rented = queryset.exists()
        if local_already_rented:
            raise ValidationError(
                'Already rented for the date'
            )


class UnitCost(models.Model):

    name = models.CharField(
        max_length=128,
        help_text='UnitCost name'
    )

    desc = models.TextField(
        null=True,
        blank=True,
        help_text='UnitCost description'
    )

    invoice_item_format = models.TextField(
        null=True,
        blank=True,
    )

    unit = models.CharField(
        max_length=128,
        help_text='Unit'
    )

    value = models.FloatField(
        help_text='Unit cost'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    removed_at = models.DateTimeField(
        null=True
    )

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='unit_costs',
    )

    def __str__(self):
        return self.name
