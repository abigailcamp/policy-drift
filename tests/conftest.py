import os


def pytest_configure():
    # Ensure admin routes are testable with a known password.
    os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")

