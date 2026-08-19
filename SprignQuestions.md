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


Global Exception Handler : 
Q1. Why do we need global exception handling?

Instead of repeating try-catch blocks in every controller method, we can centralize exception handling using @RestControllerAdvice and @ExceptionHandler. This keeps controllers clean and allows us to return a consistent error response format across the application.

Q2. What is @ExceptionHandler?

@ExceptionHandler tells Spring which controller method should handle a particular exception type. It can be used inside a controller for local handling or inside @ControllerAdvice/@RestControllerAdvice for centralized handling.

Q3. What is @RestControllerAdvice?

@RestControllerAdvice provides centralized exception handling for REST controllers and includes @ResponseBody behavior, so returned error objects are serialized directly into the HTTP response body.

Q4. Difference between @ControllerAdvice and @RestControllerAdvice?

@RestControllerAdvice is effectively @ControllerAdvice combined with @ResponseBody. It is convenient for REST APIs because handler return values are written directly to the response body.

Q5. How do you handle multiple exception types with one handler?

Use multiple exception classes in @ExceptionHandler, for example @ExceptionHandler({TypeA.class, TypeB.class}), or handle a common parent exception when the same handling behavior is appropriate.

Q6. Why create custom exceptions?

Custom exceptions allow us to represent meaningful business failures, such as UserNotFoundException or OrderNotFoundException, and map them to appropriate HTTP responses through the global exception handler.

Q7. Should the service return ResponseEntity when an exception occurs?

Generally no. The service layer should focus on business logic and can throw a meaningful exception. The web/controller layer can translate that exception into an HTTP status and response through global exception handling.

Q8. Should we return the raw exception message to the client?

Not for unexpected or internal exceptions. We should log the detailed exception server-side and return a safe, generic error message to the client to avoid exposing internal implementation or sensitive information.

Q9. What happens if no @ExceptionHandler handles an exception?

If the exception isn't handled by an application-specific handler, Spring's exception resolution mechanisms can handle it using its built-in/default handling. For production APIs, we generally define appropriate handlers for expected application errors and often have a final generic handler for unexpected failures.


Validation 
Q1. What is Bean Validation?

Bean Validation is a standard mechanism for declaring validation constraints on Java objects using annotations such as @NotBlank, @Email, @Size, and @Min. Spring Boot integrates with a validation provider such as Hibernate Validator.

Q2. What does @Valid do?

@Valid triggers validation of the object using its declared validation constraints. When used with @RequestBody, it validates the incoming request DTO before normal controller processing continues.

Q3. Difference between @NotNull, @NotEmpty, and @NotBlank?

@NotNull only rejects null. @NotEmpty rejects null and empty values but allows whitespace-only strings. @NotBlank rejects null, empty, and whitespace-only strings and is commonly used when a String must contain meaningful content.

Q4. How do you validate nested DTOs?

Add @Valid to the nested DTO field so validation cascades into the nested object's fields.

Q5. What happens when @Valid fails?

Spring raises a validation-related exception, such as MethodArgumentNotValidException for an invalid @RequestBody, which can be handled using @RestControllerAdvice and @ExceptionHandler to return a consistent 400 response.

Q6. When would you create a custom validator?

When the required validation rule cannot be adequately represented using the built-in constraints. We create a custom constraint annotation and implement its validation logic using ConstraintValidator.

Q7. Does @Email verify that the email actually exists?

No. It validates the email's format; it doesn't verify that the mailbox exists or that the user controls it.
