from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from teams.models import Team


class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'monthly'

    def items(self):
        return [
            'home',
            'teams:team_list',
            'privacy_policy',
            'terms_of_service',
            'accounts:contact',
            'bot_info',
        ]

    def location(self, item):
        return reverse(item)


class PublicTeamSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        entries = []
        for team in Team.objects.filter(hidden=False):
            slug = {'slug': team.slug}
            lastmod = team.updated_at
            entries.append(('teams:team_detail', slug, lastmod))
            entries.append(('scores:standings', slug, lastmod))
            entries.append(('scores:sessions', slug, lastmod))
        return entries

    def location(self, item):
        route_name, kwargs, _lastmod = item
        return reverse(route_name, kwargs=kwargs)

    def lastmod(self, item):
        return item[2]
