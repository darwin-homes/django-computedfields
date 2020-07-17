import django
from django.test import TestCase
from ..models import Person, Group, Membership
from django.test.utils import CaptureQueriesContext
from django.db import connection
from computedfields.models import update_dependent


class SelfDeps(TestCase):
    def setUp(self):
        self.persons = [Person.objects.create(name='P{}'.format(i)) for i in range(10)]
        self.groups = [Group.objects.create(name=g) for g in 'ABCDEFGHJI']
        if django.VERSION >= (2,2):
            self.persons[0].groups.add(self.groups[0], self.groups[1])
            self.persons[1].groups.add(self.groups[0], self.groups[1])
        else:
            Membership.objects.create(person=self.persons[0], group=self.groups[0])
            Membership.objects.create(person=self.persons[0], group=self.groups[1])
            Membership.objects.create(person=self.persons[1], group=self.groups[0])
            Membership.objects.create(person=self.persons[1], group=self.groups[1])

    def test_init(self):
        p0 = self.persons[0]
        p0.refresh_from_db()
        self.assertEqual(p0.my_groups, 'A,B')
        g0 = self.groups[0]
        g0.refresh_from_db()
        self.assertEqual(g0.my_members, 'P0,P1')
    
    def test_change_group_name(self):
        self.groups[1].name = 'b'
        self.groups[1].save(update_fields=['name'])
        p0 = self.persons[0]
        p0.refresh_from_db()
        self.assertEqual(p0.my_groups, 'A,b')
    
    def test_add_group(self):
        if django.VERSION >= (2, 2):
            Group.objects.create(name='Z').members.set([self.persons[0]])
        else:
            group = Group.objects.create(name='Z')
            Membership.objects.create(group=group, person=self.persons[0])
        p0 = self.persons[0]
        p0.refresh_from_db()
        self.assertEqual(p0.my_groups, 'A,B,Z')
        if django.VERSION >= (2, 2):
            p0.groups.create(name='X')
        else:
            group = Group.objects.create(name='X')
            Membership.objects.create(group=group, person=p0)
        p0.refresh_from_db()
        self.assertEqual(p0.my_groups, 'A,B,Z,X')

    def test_delete_group(self):
        self.groups[0].delete()
        p0 = self.persons[0]
        p0.refresh_from_db()
        self.assertEqual(p0.my_groups, 'B')

    def test_change_person_name(self):
        self.persons[1].name = 'Px'
        self.persons[1].save(update_fields=['name'])
        g0 = self.groups[0]
        g0.refresh_from_db()
        self.assertEqual(g0.my_members, 'P0,Px')

    def test_add_person(self):
        if django.VERSION >= (2, 2):
            Person.objects.create(name='Py').groups.set([self.groups[0]])
        else:
            person = Person.objects.create(name='Py')
            Membership.objects.create(person=person, group=self.groups[0])
        g0 = self.groups[0]
        g0.refresh_from_db()
        self.assertEqual(g0.my_members, 'P0,P1,Py')
        if django.VERSION >= (2, 2):
            g0.members.create(name='Pz')
        else:
            person = Person.objects.create(name='Pz')
            Membership.objects.create(group=g0, person=person)
        g0.refresh_from_db()
        self.assertEqual(g0.my_members, 'P0,P1,Py,Pz')

    def test_delete_person(self):
        self.persons[0].delete()
        g0 = self.groups[0]
        g0.refresh_from_db()
        self.assertEqual(g0.my_members, 'P1')
    
    def test_delete_through(self):
        # test manipulations on the through model
        # --> must be listed in depends to work correctly (no auto expansion on m2m internals)
        t = Membership.objects.all()[0]
        t.delete()

        p0 = self.persons[0]
        p0.refresh_from_db()
        self.assertEqual(p0.my_groups, 'B') # should be 'B', not 'A,B
        g0 = self.groups[0]
        g0.refresh_from_db()
        self.assertEqual(g0.my_members, 'P1') # should be 'P1', not 'P0,P1'
