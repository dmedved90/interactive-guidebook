"""Fields added in the EZSJ fork: service duration, cost, cost estimate and provider; step themes."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.content import ContentError, load_content
from catalog.models import Country, GeneralStep, Phase, Service, ServiceTranslation

from .test_content import ContentFilesMixin


class EzsjContentTests(ContentFilesMixin, TestCase):
    def write_extended(self, provider='external', themes='[solar]'):
        self.write('steps/planning/permits.yaml', f"""
            title: Permits
            sort_order: 10
            themes: {themes}
        """)
        self.write('services/hr/permit.yaml', f"""
            name: 'HR: Permit'
            step: permits
            summary: Get the permit.
            duration: '6-12 weeks'
            cost: High
            cost_estimate: '5,000-15,000 EUR'
            provider: {provider}
            hr:
              duration: '6-12 tjedana'
              cost: Visoka cijena
              cost_estimate: '5.000-15.000 EUR'
        """)

    def test_fields_are_synced(self):
        self.write_extended()
        self.sync()
        service = Service.objects.get(source_key='hr/permit')
        self.assertEqual(
            (service.duration, service.cost, service.cost_estimate, service.provider),
            ('6-12 weeks', 'High', '5,000-15,000 EUR', 'external'),
        )
        hr = ServiceTranslation.objects.get(service=service, language='hr')
        self.assertEqual((hr.duration, hr.cost, hr.cost_estimate), ('6-12 tjedana', 'Visoka cijena', '5.000-15.000 EUR'))
        self.assertEqual(GeneralStep.objects.get(source_key='permits').theme_list, ['solar'])

    def test_removing_fields_clears_them(self):
        self.write_extended()
        self.sync()
        self.write('steps/planning/permits.yaml', "title: Permits\nsort_order: 10\n")
        self.write('services/hr/permit.yaml', "name: 'HR: Permit'\nstep: permits\nsummary: Get the permit.\n")
        self.sync()
        service = Service.objects.get(source_key='hr/permit')
        self.assertEqual((service.duration, service.cost, service.cost_estimate, service.provider), ('', '', '', ''))
        self.assertEqual(GeneralStep.objects.get(source_key='permits').themes, '')

    def test_unknown_provider_is_rejected(self):
        self.write_extended(provider='someone')
        with self.assertRaises(ContentError) as ctx:
            load_content(self.dir)
        self.assertIn('"provider" must be one of', '\n'.join(ctx.exception.errors))

    def test_unknown_theme_is_rejected(self):
        self.write_extended(themes='[wind]')
        with self.assertRaises(ContentError) as ctx:
            load_content(self.dir)
        self.assertIn('"themes" must be a list of', '\n'.join(ctx.exception.errors))


class EzsjViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # An existing account, so the first-run setup redirect does not apply.
        get_user_model().objects.create_user('manager@example.com', password='pw')
        croatia = Country.objects.create(code='HR', name='Croatia', language='hr')
        planning = Phase.objects.get(slug='planning')
        operation = Phase.objects.get(slug='operation')
        cls.solar_step = GeneralStep.objects.create(title='Grid analysis', phase=planning, sort_order=1, themes='solar')
        cls.other_step = GeneralStep.objects.create(title='Community building', phase=planning, sort_order=2)
        GeneralStep.objects.create(title='Billing', phase=operation, sort_order=3)
        cls.service = Service.objects.create(
            name='HR: Grid', slug='hr-grid', summary='S', country=croatia, general_step=cls.solar_step,
            duration='4-8 weeks', cost='Medium', cost_estimate='1,500-4,000 EUR', provider='oss',
        )
        ServiceTranslation.objects.create(
            service=cls.service, language='hr', duration='4-8 tjedana', cost='Srednja cijena',
            cost_estimate='1.500-4.000 EUR',
        )

    def step_titles(self, response):
        return [item['step'].title for pd in response.context['phase_data'] for item in pd['steps']]

    def test_guidebook_without_theme_shows_all_steps(self):
        response = self.client.get(reverse('catalog:guidebook'))
        self.assertEqual(self.step_titles(response), ['Grid analysis', 'Community building', 'Billing'])
        self.assertContains(response, '4-8 weeks')
        self.assertContains(response, '1,500-4,000 EUR')

    def test_theme_filter_shows_only_theme_steps_and_hides_empty_phases(self):
        response = self.client.get(reverse('catalog:guidebook'), {'theme': 'solar'})
        self.assertEqual(self.step_titles(response), ['Grid analysis'])
        self.assertEqual([pd['phase'].slug for pd in response.context['phase_data']], ['planning'])
        self.assertEqual((response.context['shown_steps'], response.context['total_steps']), (1, 3))

    def test_unknown_theme_is_ignored(self):
        response = self.client.get(reverse('catalog:guidebook'), {'theme': 'wind'})
        self.assertEqual(len(self.step_titles(response)), 3)

    def test_service_page_shows_facts_in_selected_language(self):
        url = reverse('catalog:service_detail', args=[self.service.slug])
        response = self.client.get(url)
        self.assertContains(response, '4-8 weeks')
        self.assertContains(response, 'Medium')
        response = self.client.get(url, {'text': 'hr'})
        self.assertContains(response, '4-8 tjedana')
        self.assertContains(response, 'Srednja cijena')
