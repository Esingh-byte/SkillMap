from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from roadmaps.models import Category, Node, Roadmap, RoadmapBookmark
from roadmaps.services import search_roadmaps


class BookmarkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("alice", password="pw12345!")
        cls.other_user = User.objects.create_user("bob", password="pw12345!")
        cls.pub = Roadmap.objects.create(
            title="Published Python", slug="published-python", is_published=True
        )
        cls.other_pub = Roadmap.objects.create(
            title="Other Published", slug="other-published", is_published=True
        )
        cls.draft = Roadmap.objects.create(
            title="Draft Secret", slug="draft-secret", is_published=False
        )
        cls.bookmark_url = reverse("roadmaps:bookmark", args=[cls.pub.slug])

    def test_anonymous_redirected_to_login(self):
        resp = self.client.post(self.bookmark_url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts:login"), resp["Location"])
        self.assertFalse(RoadmapBookmark.objects.exists())

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.bookmark_url)
        self.assertEqual(resp.status_code, 405)

    def test_unpublished_roadmap_rejected_404(self):
        self.client.force_login(self.user)
        url = reverse("roadmaps:bookmark", args=[self.draft.slug])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(RoadmapBookmark.objects.exists())

    def test_toggle_on_and_off_htmx_returns_partial(self):
        self.client.force_login(self.user)

        # Toggle ON via HTMX
        resp_on = self.client.post(self.bookmark_url, HTTP_HX_REQUEST="true")
        self.assertEqual(resp_on.status_code, 200)
        self.assertTrue(
            RoadmapBookmark.objects.filter(user=self.user, roadmap=self.pub).exists()
        )
        self.assertContains(resp_on, "Saved")
        self.assertNotContains(resp_on, "<html")

        # Toggle OFF via HTMX
        resp_off = self.client.post(self.bookmark_url, HTTP_HX_REQUEST="true")
        self.assertEqual(resp_off.status_code, 200)
        self.assertFalse(
            RoadmapBookmark.objects.filter(user=self.user, roadmap=self.pub).exists()
        )
        self.assertContains(resp_off, "Save")

    def test_toggle_on_and_off_non_js_redirects_with_message(self):
        self.client.force_login(self.user)
        list_url = reverse("roadmaps:list")

        resp_on = self.client.post(
            self.bookmark_url, {"next": list_url}, follow=True
        )
        self.assertEqual(resp_on.status_code, 200)
        self.assertTrue(
            RoadmapBookmark.objects.filter(user=self.user, roadmap=self.pub).exists()
        )
        self.assertContains(resp_on, "Saved")

        resp_off = self.client.post(
            self.bookmark_url, {"next": list_url}, follow=True
        )
        self.assertEqual(resp_off.status_code, 200)
        self.assertFalse(
            RoadmapBookmark.objects.filter(user=self.user, roadmap=self.pub).exists()
        )
        self.assertContains(resp_off, "Removed")

    def test_saved_roadmaps_page_shows_only_my_bookmarks_and_empty_state(self):
        saved_url = reverse("roadmaps:saved")

        # Anonymous redirected
        self.assertEqual(self.client.get(saved_url).status_code, 302)

        # Empty state for alice
        self.client.force_login(self.user)
        empty_resp = self.client.get(saved_url)
        self.assertEqual(empty_resp.status_code, 200)
        self.assertContains(empty_resp, "No saved roadmaps yet.")

        # Bob bookmarks other_pub; Alice bookmarks pub
        RoadmapBookmark.objects.create(user=self.other_user, roadmap=self.other_pub)
        RoadmapBookmark.objects.create(user=self.user, roadmap=self.pub)

        resp = self.client.get(saved_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.pub.title)
        self.assertNotContains(resp, self.other_pub.title)


class RoadmapSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cat_data = Category.objects.create(name="Data Science", slug="data-science")
        cls.cat_web = Category.objects.create(name="Web Development", slug="web-dev")

        # Matches "kubernetes" only in description (alphabetically earlier title "Alpha Ops")
        cls.rm_desc_match = Roadmap.objects.create(
            title="Alpha Ops",
            slug="alpha-ops",
            description="Deploy containers with Kubernetes clusters.",
            category=cls.cat_web,
            is_published=True,
        )
        # Matches "kubernetes" in title (alphabetically later title "Zulu Kubernetes")
        cls.rm_title_match = Roadmap.objects.create(
            title="Zulu Kubernetes Mastery",
            slug="zulu-k8s",
            description="Container orchestration guide.",
            category=cls.cat_web,
            is_published=True,
        )
        # Matches by category name ("Data Science") and has multiple nodes matching "Pandas"
        cls.rm_cat_and_nodes = Roadmap.objects.create(
            title="Analytics Track",
            slug="analytics-track",
            description="Learn tabular analysis.",
            category=cls.cat_data,
            is_published=True,
        )
        Node.objects.create(
            roadmap=cls.rm_cat_and_nodes,
            title="Pandas DataFrames",
            slug="pandas-df",
            order=1,
        )
        Node.objects.create(
            roadmap=cls.rm_cat_and_nodes,
            title="Pandas GroupBy and Joins",
            slug="pandas-groupby",
            order=2,
        )

        # Unpublished roadmap matching everything — must never appear
        cls.rm_unpublished = Roadmap.objects.create(
            title="Kubernetes Pandas Data Science Secret",
            slug="secret-unpublished",
            description="Kubernetes Pandas Data Science",
            category=cls.cat_data,
            is_published=False,
        )

    def test_search_by_each_field_and_unpublished_hidden(self):
        # By title
        by_title = list(search_roadmaps("Mastery"))
        self.assertEqual(by_title, [self.rm_title_match])

        # By description
        by_desc = list(search_roadmaps("tabular analysis"))
        self.assertEqual(by_desc, [self.rm_cat_and_nodes])

        # By category name
        by_cat = list(search_roadmaps("data science"))
        self.assertEqual(by_cat, [self.rm_cat_and_nodes])

        # By node title (must return distinct roadmap with no duplicates even though 2 nodes match)
        by_node = list(search_roadmaps("pandas"))
        self.assertEqual(by_node, [self.rm_cat_and_nodes])
        self.assertEqual(len(by_node), 1)

    def test_title_matches_ranked_above_description_only_matches(self):
        results = list(search_roadmaps("kubernetes"))
        self.assertEqual(results, [self.rm_title_match, self.rm_desc_match])

    def test_combined_search_and_category_filter(self):
        # Both analytics-track and alpha-ops have 'a', filter by data-science category
        results = list(search_roadmaps("pandas", category="data-science"))
        self.assertEqual(results, [self.rm_cat_and_nodes])

        empty = list(search_roadmaps("pandas", category="web-dev"))
        self.assertEqual(empty, [])

    def test_pagination_at_12_keeps_q_and_category_in_links(self):
        for i in range(1, 15):
            Roadmap.objects.create(
                title=f"Searchable Topic {i:02d}",
                slug=f"searchable-topic-{i:02d}",
                description="Common keyword xylophone",
                category=self.cat_web,
                is_published=True,
            )

        resp = self.client.get(
            reverse("roadmaps:list"),
            {"q": "xylophone", "category": "web-dev"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["roadmaps"]), 12)
        self.assertTrue(resp.context["page_obj"].has_other_pages())
        self.assertContains(resp, "?page=2&q=xylophone&category=web-dev")
