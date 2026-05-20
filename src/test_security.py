from copy import deepcopy
from fastapi.testclient import TestClient
from src.main import _files_seed, app, files_db

client = TestClient(app)

def reset_files_db() -> None:
    files_db[:] = deepcopy(_files_seed)

def run_tests() -> None:
    reset_files_db()

    response_1 = client.get("/files/2", headers={"X-User-Id": "1"})
    if response_1.status_code != 404:  # nosec - test assertion
        raise AssertionError(f"Expected 404, got {response_1.status_code}: {response_1.text}")
    print("Test 1 passed: User A cannot read User B file (404)")

    response_2 = client.get("/files/1", headers={"X-User-Id": "1"})
    if response_2.status_code != 200:  # nosec - test assertion
        raise AssertionError(f"Expected 200, got {response_2.status_code}: {response_2.text}")
    print("Test 2 passed: User A can read own file (200)")

    response_3 = client.delete("/files/2", headers={"X-User-Id": "3"})
    if response_3.status_code != 200:  # nosec - test assertion
        raise AssertionError(f"Expected 200, got {response_3.status_code}: {response_3.text}")
    after_delete = client.get("/files/2", headers={"X-User-Id": "3"})
    if after_delete.status_code != 404:  # nosec - test assertion
        raise AssertionError(f"Expected 404, got {after_delete.status_code}: {after_delete.text}")
    print("Test 3 passed: Admin deleted User B file (200 + removed)")

    print("All security tests passed.")

if __name__ == "__main__":
    run_tests()
