import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  thresholds: {
    http_req_duration: ["p(99) < 30000"],
  },
  stages: [
    { duration: "30s", target: 15 },
    { duration: "1m", target: 15 },
    { duration: "20s", target: 0 },
  ],
};

const servers = ["http://localhost:8000", "http://localhost:8001", "http://localhost:8002"];
const endpoints = ["/", "/products/42?q=test", "/charge_card", "/calculate_tax", "/random_status", "/random_sleep", "/checkout", "/error_test"];

export default function () {
  for (const server of servers) {
    for (const endpoint of endpoints) {
      let res = http.get(`${server}${endpoint}`);
      check(res, { [`${server}${endpoint}`]: (r) => r.status < 600 });
    }
  }
  sleep(0.5);
}
