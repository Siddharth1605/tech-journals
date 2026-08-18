RESTController Interview Questions
Q1. What is @RestController?

> @RestController is a convenience annotation combining @Controller and @ResponseBody. It is commonly used for REST APIs because controller method return values are written directly to the HTTP response body and are typically serialized as JSON.




---

Q2. Difference between @PathVariable and @RequestParam?

> @PathVariable extracts values from the URL path, such as /users/10, while @RequestParam extracts values from query parameters, such as /users?name=avi.




---

Q3. What is @RequestBody?

> @RequestBody tells Spring to deserialize the HTTP request body into a Java object, typically using an HTTP message converter such as Jackson for JSON.




---

Q4. Why use ResponseEntity?

> ResponseEntity provides explicit control over the HTTP response, including status code, headers, and body. It's useful when the endpoint needs to return statuses such as 201 Created or 204 No Content instead of simply returning a body with the default response handling.




---

Q5. Should POST always return 201?

> No. When POST successfully creates a new resource, 201 Created is the appropriate status. But POST can legitimately return other status codes depending on what the operation does.




---

Q6. How do class-level and method-level mappings work?

> The class-level mapping acts as the base path, and the method-level mapping is combined with it. For example, @RequestMapping("/api/users") and @GetMapping("/{id}") produce GET /api/users/{id}.




---

Q7. Difference between @Controller and @RestController?

> @Controller is typically used for Spring MVC controllers that may return views. @RestController combines @Controller with @ResponseBody, so return values are written directly to the response body, which is convenient for REST APIs.

