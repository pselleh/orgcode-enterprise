from django.test import SimpleTestCase

from orgcode_enterprise.management.commands.import_access_policy_manifest import Command


class AccessPolicyManifestTests(SimpleTestCase):
    def test_organization_code_courses_are_selected(self):
        payload = {
            "courses": [
                {
                    "course_key": "course-v1:CBA+ETR211+2027",
                    "access_scope": "organization_code",
                    "access_policy_key": "cba-restricted-risk-intelligence-2027",
                },
                {
                    "course_key": "course-v1:CBA+PUBLIC101+2027",
                    "access_scope": "public",
                    "access_policy_key": "",
                },
            ]
        }
        courses, programs, errors = Command()._validate(
            payload, "cba-restricted-risk-intelligence-2027"
        )
        self.assertEqual(courses, {"course-v1:CBA+ETR211+2027"})
        self.assertEqual(programs, set())
        self.assertEqual(errors, [])

    def test_policy_key_mismatch_is_rejected(self):
        payload = {
            "courses": [
                {
                    "course_key": "course-v1:CBA+ETR211+2027",
                    "access_scope": "organization_code",
                    "access_policy_key": "wrong-policy",
                }
            ]
        }
        _courses, _programs, errors = Command()._validate(
            payload, "cba-restricted-risk-intelligence-2027"
        )
        self.assertTrue(any("must equal" in error for error in errors))
