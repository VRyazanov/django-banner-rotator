#-*- coding:utf-8 -*-

import logging

from django import forms, template
from django.contrib import admin
from django.contrib.admin.util import unquote
from django.db import models
from django.db.models import Q
from django.shortcuts import get_object_or_404, render_to_response
from django.utils.encoding import force_unicode
from functools import update_wrapper
from django.utils.text import capfirst
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from banner_rotator.forms import BannerForm

from banner_rotator.models import Campaign, Place, Banner, Click


class PlaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'size_str')
    prepopulated_fields = {'slug': ('name',)}


class CampaignBannerInline(admin.StackedInline):
    model = Banner
    extra = 0
    
    clicks = lambda banner: banner.clicks.all().count()
    clicks.short_description = _('clicks')
    
    readonly_fields = ['views', clicks]
    fields = ['in_rotation', 'places', 'name', 'url', 'file', 'weight', 'views', clicks]
    filter_horizontal = ('places',)


class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'updated_at', 'start_at', 'finish_at', 'is_started')
    fields = ('name', 'start_at', 'finish_at')
    list_editable = ['start_at', 'finish_at']
    inlines = [CampaignBannerInline]
    actions = ['start_campaign', 'finish_campaign']

    def start_campaign(self, request, queryset):
        for campaign in queryset:
            start_at = campaign.start_at if campaign.start_at else now()
            finish_at = campaign.finish_at if campaign.finish_at else None
            campaign.banners.update(start_at=start_at, finish_at=finish_at, in_rotation=True)
            campaign.start_at = start_at
            campaign.finish_at = finish_at
            campaign.is_started = True
            campaign.save()
        queryset.update()
    start_campaign.short_description = _('Start selected campaigns')

    def finish_campaign(self, request, queryset):
        for campaign in queryset:
            campaign.banners.update(in_rotation=False)
            campaign.finish_at = now()
            campaign.is_started = False
            campaign.save()
    finish_campaign.short_description = _('Finish selected campaigns')


class BannerAdmin(admin.ModelAdmin):
    form = BannerForm
    list_display = ('name', 'campaign', 'weight', 'url', 'views', 'in_rotation')
    list_filter = ('campaign', 'places', 'in_rotation')
    date_hierarchy = 'created_at'
    actions = ['start_multiple_banners_indefinitely', 'start_all_actual_banners']
    
    clicks = lambda banner: banner.clicks.all().count()
    clicks.short_description = _('clicks')
    
    fieldsets = (
        (_('Main'), {
            'fields': ('campaign', 'places', 'name', 'url', 'url_target', 'file', 'alt'),
        }),
        (_('Show'), {
            'fields': ('weight', 'views', 'max_views', clicks, 'max_clicks', 'start_at', 'finish_at', 'in_rotation'),
        })
    )

    filter_horizontal = ('places',)
    readonly_fields = ('views', clicks,)

    object_log_clicks_template = None

    def start_multiple_banners_indefinitely(self, request, queryset):
        queryset.filter(campaign__isnull=True).update(start_at=now(), finish_at=None, in_rotation=True)
    start_multiple_banners_indefinitely.short_description = _('Start multiple banners indefinitely')

    def start_all_actual_banners(self, request, queryset):
        queryset.filter(campaign__isnull=True).filter(Q(finish_at__gt=now()) | Q(finish_at__isnull=True))\
            .update(in_rotation=True)
    start_all_actual_banners.short_description = _('Start all actual banners')

    def get_urls(self):
        try:
            # Django 1.4
            from django.conf.urls import patterns, url
        except ImportError:
            from django.conf.urls.defaults import patterns, url

        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)
            return update_wrapper(wrapper, view)

        info = self.model._meta.app_label, self.model._meta.module_name

        urlpatterns = patterns('',
            url(r'^$', wrap(self.changelist_view), name='%s_%s_changelist' % info),
            url(r'^add/$', wrap(self.add_view), name='%s_%s_add' % info),
            url(r'^(.+)/history/$', wrap(self.history_view), name='%s_%s_history' % info),
            url(r'^(.+)/delete/$', wrap(self.delete_view), name='%s_%s_delete' % info),
            url(r'^(.+)/log/clicks/$', wrap(self.log_clicks_view), name='%s_%s_log_clicks' % info),
            url(r'^(.+)/$', wrap(self.change_view), name='%s_%s_change' % info),
        )
        return urlpatterns

    def log_clicks_view(self, request, object_id, extra_context=None):
        model = self.model
        opts = model._meta
        app_label = opts.app_label

        obj = get_object_or_404(model, pk=unquote(object_id))

        context = {
            'title': _('Log clicks'),
            'module_name': capfirst(force_unicode(opts.verbose_name_plural)),
            'object': obj,
            'app_label': app_label,
            'log_clicks': Click.objects.filter(banner=obj).order_by('-datetime')
        }
        context.update(extra_context or {})
        context_instance = template.RequestContext(request, current_app=self.admin_site.name)
        return render_to_response(self.object_log_clicks_template or [
            "admin/%s/%s/object_log_clicks.html" % (app_label, opts.object_name.lower()),
            "admin/%s/object_log_clicks.html" % app_label,
        ], context, context_instance=context_instance)


admin.site.register(Banner, BannerAdmin)
admin.site.register(Campaign, CampaignAdmin)
admin.site.register(Place, PlaceAdmin)
