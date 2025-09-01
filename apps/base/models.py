import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _


class BaseQuerySet(QuerySet):
    def delete(self):
        return super(BaseQuerySet, self).update(is_deleted=True)

    def hard_delete(self):
        return super(BaseQuerySet, self).delete()

    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)


class BaseManager(models.Manager):
    def __init__(self, *args, **kwargs):
        self.alive_only = kwargs.pop('alive_only', True)
        super(BaseManager, self).__init__(*args, **kwargs)

    def get_queryset(self):
        if self.alive_only:
            return BaseQuerySet(self.model).filter(is_deleted=False)
        return BaseQuerySet(self.model)

    def hard_delete(self):
        return self.get_queryset().hard_delete()


class Base(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    created_at = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Last Updated Date"), auto_now=True)
    created_by = models.ForeignKey(
        get_user_model(), related_name='%(app_label)s_%(class)s_created_related', null=True,
        blank=True,
        on_delete=models.CASCADE
    )
    updated_by = models.ForeignKey(
        get_user_model(), related_name='%(app_label)s_%(class)s_updated_related', null=True,
        blank=True, on_delete=models.CASCADE
    )
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    objects = BaseManager()
    all_objects = BaseManager(alive_only=False)

    class Meta:
        abstract = True

    def delete(self):
        self.is_deleted = True
        self.save()

    def hard_delete(self):
        super(Base, self).delete()

    def save(self, *args, **kwargs):
        super(Base, self).save(*args, **kwargs)
