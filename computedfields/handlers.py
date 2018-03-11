from computedfields.models import ComputedFieldsModelType as CFMT
from threading import local
from django.db.models.fields.reverse_related import ManyToManyRel
from collections import OrderedDict


STORAGE = local()
STORAGE.DELETES = {}
STORAGE.M2M_REMOVE = {}
STORAGE.M2M_CLEAR = {}

DELETES = STORAGE.DELETES
M2M_REMOVE = STORAGE.M2M_REMOVE
M2M_CLEAR = STORAGE.M2M_CLEAR


def postsave_handler(sender, instance, **kwargs):
    # do not update for fixtures
    if not kwargs.get('raw'):
        CFMT.update_dependent(instance, sender, kwargs.get('update_fields'))


def predelete_handler(sender, instance, **kwargs):
    # get the querysets as pk lists to hold them in storage
    # we have to get pks here since the queryset will be empty after deletion
    data = CFMT._querysets_for_update(sender, instance, pk_list=True)
    if data:
        DELETES[instance] = data


def postdelete_handler(sender, instance, **kwargs):
    # after deletion we can update the associated computed fields
    updates = DELETES.pop(instance, {})
    for model, data in updates.items():
        pks, fields = data
        qs = model.objects.filter(pk__in=pks)
        for el in qs.distinct():
            el.save(update_fields=fields)


def m2m_handler(sender, instance, **kwargs):
    # since the graph does not handle the m2m through model
    # we have to trigger updates for both ends:
    #   - instance:   CFMT.update_dependent(instance, type(instance))
    #   - other side: CFMT.update_dependent(model.objects.filter(pk__in=pks), model)
    # TODO: might lead to nonsense double updates - How to avoid? - Resolve through models?
    action = kwargs.get('action')
    model = kwargs['model']

    if action == 'post_add':
        pks = kwargs['pk_set']
        CFMT.update_dependent(instance, type(instance))
        CFMT.update_dependent(model.objects.filter(pk__in=pks), model)

    elif action == 'pre_remove':
        data = OrderedDict()

        # instance updates
        to_add = CFMT._querysets_for_update(type(instance), instance, pk_list=True)
        if to_add:
            data.update(to_add)

        # other side updates
        pks = kwargs['pk_set']
        to_add = CFMT._querysets_for_update(model, model.objects.filter(pk__in=pks), pk_list=True)
        if to_add:
            data.update(to_add)

        # final
        if data:
            M2M_REMOVE[instance] = data

    elif action == 'post_remove':
        updates = M2M_REMOVE.pop(instance, {})
        for model, data in updates.items():
            pks, fields = data
            qs = model.objects.filter(pk__in=pks)
            for el in qs.distinct():
                el.save(update_fields=fields)

    elif action == 'pre_clear':
        data = OrderedDict()

        # instance updates
        to_add = CFMT._querysets_for_update(type(instance), instance, pk_list=True)
        if to_add:
            data.update(to_add)

        # other side updates
        # geez - have to get pks of other side ourself
        if kwargs['reverse']:
            inst_model = type(instance)
            rel = filter(lambda f: isinstance(f, ManyToManyRel) and f.through == sender,
                         inst_model._meta.get_fields())[0]
            to_add = CFMT._querysets_for_update(
                model, getattr(instance, rel.name).all(), pk_list=True)
        else:
            inst_model = type(instance)
            field = filter(lambda f: f.rel.through == sender,
                           inst_model._meta.many_to_many)[0]
            to_add = CFMT._querysets_for_update(
                model, getattr(instance, field.name).all(), pk_list=True)
        if to_add:
            data.update(to_add)

        # final
        if data:
            M2M_CLEAR[instance] = data

    elif action == 'post_clear':
        updates = M2M_CLEAR.pop(instance, {})
        for model, data in updates.items():
            pks, fields = data
            qs = model.objects.filter(pk__in=pks)
            for el in qs.distinct():
                el.save(update_fields=fields)