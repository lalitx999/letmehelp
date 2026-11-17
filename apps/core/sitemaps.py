from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.courses.selectors.course_selector import published_courses_for_sitemap


class StaticSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return ["core:home", "courses:list", "core:free_trial", "core:guide", "core:privacy", "core:terms"]

    def location(self, item):
        return reverse(item)


class CourseSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return published_courses_for_sitemap()

    def lastmod(self, obj):
        return obj.updated_at


SITEMAPS = {"static": StaticSitemap, "courses": CourseSitemap}
