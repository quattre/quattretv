from django import forms
from django.contrib import admin

from apps.devices.models import DeviceType

from .models import CdnServer, Channel


class ChannelAdminForm(forms.ModelForm):
    """
    El campo "oculto para" se guarda como texto entre comas para poder
    filtrarlo en la consulta, pero en el panel se maneja con casillas: nadie
    tiene que acordarse de como se escribe cada tipo de aparato ni de las comas.
    """

    oculto_para = forms.MultipleChoiceField(
        choices=DeviceType.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Oculto para',
        help_text='Aparatos que NO veran este canal. Sin marcar nada, lo ven todos.',
    )

    class Meta:
        model = Channel
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['oculto_para'] = self.instance.tipos_ocultos

    def clean_oculto_para(self):
        return Channel.marca(self.cleaned_data.get('oculto_para'))


@admin.register(CdnServer)
class CdnServerAdmin(admin.ModelAdmin):
    list_display = ('name', 'hls_base_url', 'ssh_host', 'ssh_port', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'hls_base_url', 'ssh_host')
from .models import Category, Channel, ChannelPackage, ChannelStream, Favorite


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'alias', 'parent', 'order', 'is_adult', 'is_active')
    list_filter = ('is_active', 'is_adult', 'parent')
    search_fields = ('name', 'alias')
    prepopulated_fields = {'alias': ('name',)}
    ordering = ('order', 'name')


class ChannelStreamInline(admin.TabularInline):
    model = ChannelStream
    extra = 1


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    form = ChannelAdminForm
    list_display = (
        'number', 'name', 'category', 'is_hd', 'is_4k',
        'has_epg', 'has_timeshift', 'oculto_en', 'is_active'
    )
    list_filter = ('category', 'is_active', 'is_hd', 'is_4k', 'is_adult', 'has_epg', 'has_timeshift')

    @admin.display(description='Oculto para')
    def oculto_en(self, obj):
        return ', '.join(obj.tipos_ocultos) or '-'

    search_fields = ('name', 'number', 'epg_id')
    filter_horizontal = ('packages',)
    inlines = [ChannelStreamInline]
    ordering = ('number',)

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'number', 'category', 'description')
        }),
        ('Logo', {
            'fields': ('logo', 'logo_url')
        }),
        ('Streaming', {
            'fields': ('stream_url', 'stream_type', 'backup_stream_url')
        }),
        ('Features', {
            'fields': (
                'has_epg', 'has_timeshift', 'has_catchup', 'has_recording',
                'is_hd', 'is_4k', 'is_adult'
            )
        }),
        ('Quien ve este canal', {
            'fields': ('oculto_para',),
            'description': 'La tarifa dice que canales tiene contratados el '
                           'CLIENTE. Esto dice en que APARATOS se pueden ver, '
                           'que no es lo mismo: un cliente puede tener un MAG y '
                           'una LG con la misma tarifa. Se usa, por ejemplo, '
                           'para no mandar canales +18 a los televisores LG, '
                           'que no los admiten sin un contrato aparte con LG.',
        }),
        ('EPG & Timeshift', {
            'fields': ('epg_id', 'timeshift_hours')
        }),
        ('Packages & Metadata', {
            'fields': ('packages', 'country', 'language', 'is_active')
        }),
    )


@admin.register(ChannelPackage)
class ChannelPackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    search_fields = ('name',)


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'channel', 'order', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'channel__name')
