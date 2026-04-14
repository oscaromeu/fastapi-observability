import http from "k6/http";
import { check } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export default function () {
  let res = http.get(`${BASE_URL}/`);
  check(res, { "root 200": (r) => r.status === 200 });

  res = http.get(`${BASE_URL}/io_task`);
  check(res, { "io_task 200": (r) => r.status === 200 });

  res = http.get(`${BASE_URL}/cpu_task`);
  check(res, { "cpu_task 200": (r) => r.status === 200 });

  res = http.get(`${BASE_URL}/items/42?q=test`);
  check(res, { "items 200": (r) => r.status === 200 });

  res = http.get(`${BASE_URL}/random_status`);
  check(res, { "random_status not 500": (r) => r.status !== 500 });

  res = http.get(`${BASE_URL}/random_sleep`);
  check(res, { "random_sleep 200": (r) => r.status === 200 });

  res = http.get(`${BASE_URL}/chain`);
  check(res, { "chain 200": (r) => r.status === 200 });

  res = http.get(`${BASE_URL}/error_test`);
  check(res, { "error_test 500": (r) => r.status === 500 });
}
