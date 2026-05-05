import http from "k6/http";
import { check } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export default function () {
  let res = http.get(`${BASE_URL}/`);
  check(res, { "root 200": (r) => r.status === 200 });

  res = http.get(`${BASE_URL}/charge_card`);
  check(res, { "charge_card 200": (r) => r.status === 200 });

  res = http.get(`${BASE_URL}/calculate_tax`);
  check(res, { "calculate_tax 200": (r) => r.status === 200 });

  res = http.get(`${BASE_URL}/products/42?q=test`);
  check(res, { "products 200": (r) => r.status === 200 });

  res = http.get(`${BASE_URL}/random_status`);
  check(res, { "random_status not 500": (r) => r.status !== 500 });

  res = http.get(`${BASE_URL}/random_sleep`);
  check(res, { "random_sleep 200": (r) => r.status === 200 });

  res = http.get(`${BASE_URL}/checkout`);
  check(res, { "checkout 200": (r) => r.status === 200 });

  res = http.get(`${BASE_URL}/error_test`);
  check(res, { "error_test 500": (r) => r.status === 500 });
}
