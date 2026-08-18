4. REST Controllers & Request Mappings

1. What is a REST Controller?

In a Spring Boot application, a REST Controller is a class that handles HTTP requests and returns data, usually JSON, to the client.

Example:

@RestController
@RequestMapping("/api/users")
public class UserController {
    
}

@RestController tells Spring:

> "This class handles HTTP requests, and the return values of its methods should be written directly to the HTTP response body."



It is effectively:

@RestController
      =
@Controller
      +
@ResponseBody

@Controller

Marks a class as a Spring MVC controller.

Traditionally, a controller could return a view name:

@Controller
public class UserController {

    @GetMapping("/users")
    public String users() {
        return "users";
    }
}

Spring may interpret "users" as a view to render.

@ResponseBody

Tells Spring:

> "Don't interpret the return value as a view. Put it directly into the HTTP response body."



For REST APIs, the returned Java object is typically serialized to JSON.

For example:

@GetMapping("/users")
public User getUser() {
    return user;
}

might produce:

{
  "id": 10,
  "name": "Avi"
}

Therefore, @RestController is convenient for REST APIs because you don't need to put @ResponseBody on every method.


---

2. What is Request Mapping?

Request mapping means:

> Mapping an incoming HTTP request to the appropriate controller method.



For example:

@GetMapping("/users")
public List<UserDto> getUsers() {
    ...
}

means:

GET /users
       ↓
getUsers()

Spring examines things such as:

HTTP method (GET, POST, PUT, DELETE, etc.)

URL/path

request parameters

headers, when configured


and determines which controller method should handle the request.


---

3. @RequestMapping at Class Level

Consider:

@RestController
@RequestMapping("/api/users")
public class UserController {

    @GetMapping("/{id}")
    public UserDto getUser(@PathVariable Long id) {
        ...
    }
}

The class-level mapping:

@RequestMapping("/api/users")

acts as the base path.

The method-level mapping:

@GetMapping("/{id}")

is added to it.

Therefore the complete endpoint is:

GET /api/users/{id}

For example:

GET /api/users/5

calls:

getUser(5);


---

4. Common Mapping Annotations

You should know these:

Annotation	HTTP method	Example

@GetMapping	GET	Retrieve data
@PostMapping	POST	Create resource
@PutMapping	PUT	Replace/update resource
@PatchMapping	PATCH	Partial update
@DeleteMapping	DELETE	Delete resource
@RequestMapping	Any/configurable	General-purpose mapping


For example:

@GetMapping("/users")
@PostMapping("/users")
@PutMapping("/users/{id}")
@PatchMapping("/users/{id}")
@DeleteMapping("/users/{id}")


---

5. @PathVariable

@PathVariable gets a value from the URL path.

Example:

@GetMapping("/{id}")
public UserDto getUser(@PathVariable Long id) {
    ...
}

Request:

GET /api/users/5

Then:

id = 5

Think:

/api/users/5
            ↑
        Path Variable

Another example:

@GetMapping("/{userId}/orders/{orderId}")
public OrderDto getOrder(
        @PathVariable Long userId,
        @PathVariable Long orderId) {
    ...
}

Request:

GET /api/users/10/orders/500

gives:

userId = 10
orderId = 500

Interview definition

> @PathVariable is used to extract a value from a variable part of the URL path.




---

6. @RequestParam

@RequestParam gets a value from the query string.

Example:

@GetMapping
public List<UserDto> search(
        @RequestParam(required = false) String name) {
    ...
}

Request:

GET /api/users?name=avi

Then:

name = "avi"

Think:

/api/users?name=avi
            ↑
       Query parameter

You can have multiple parameters:

@GetMapping
public List<UserDto> search(
        @RequestParam String name,
        @RequestParam Integer age) {
    ...
}

Request:

GET /api/users?name=avi&age=23


---

required = false

This:

@RequestParam(required = false) String name

means the parameter is optional.

So both are valid:

GET /api/users

and:

GET /api/users?name=avi

If you don't specify required = false, request parameters are generally required by default.


---

7. @RequestBody

@RequestBody reads data from the HTTP request body and converts it into a Java object.

For example:

@PostMapping
public UserDto create(@RequestBody UserDto dto) {
    ...
}

Client sends:

POST /api/users
Content-Type: application/json

with:

{
  "name": "Avi",
  "email": "avi@example.com"
}

Spring converts that JSON into:

UserDto dto

Conceptually:

JSON request body
       ↓
HTTP message converter
       ↓
UserDto Java object
       ↓
Controller method

For JSON, Jackson is commonly used for this serialization/deserialization in Spring Boot.

Interview definition

> @RequestBody tells Spring to deserialize the HTTP request body into the specified Java object.




---

8. @Valid

You will commonly see:

@PostMapping
public ResponseEntity<UserDto> create(
        @RequestBody @Valid UserDto dto) {
    ...
}

@Valid triggers validation of the incoming object based on validation annotations.

For example:

public class UserDto {

    @NotBlank
    private String name;

    @Email
    private String email;
}

If the request contains:

{
  "name": "",
  "email": "hello"
}

validation can fail before your controller method proceeds normally.

For a 1.5 YOE interview, know the basic idea:

> @Valid triggers Bean Validation on the request object.




---

9. Complete Controller Example

@RestController
@RequestMapping("/api/users")
public class UserController {

    @GetMapping("/{id}")
    public ResponseEntity<UserDto> getUser(
            @PathVariable Long id) {

        UserDto user = userService.findById(id);

        return ResponseEntity.ok(user);
    }

    @PostMapping
    public ResponseEntity<UserDto> create(
            @RequestBody @Valid UserDto dto) {

        UserDto saved = userService.save(dto);

        return ResponseEntity
                .status(HttpStatus.CREATED)
                .body(saved);
    }

    @GetMapping
    public List<UserDto> search(
            @RequestParam(required = false) String name) {

        return userService.search(name);
    }
}

Now look at the resulting APIs:

GET /api/users/10
             ↑
        @PathVariable

GET /api/users?name=avi
                  ↑
             @RequestParam

POST /api/users
     +
JSON body
     ↓
@RequestBody


---

10. What is ResponseEntity?

This is important for interviews.

Suppose you write:

@GetMapping("/{id}")
public UserDto getUser(@PathVariable Long id) {
    return userService.findById(id);
}

Spring will serialize the object into the response body.

For a normal successful response, you'll commonly get:

HTTP 200 OK

But sometimes you need more control over the HTTP response.

That's where ResponseEntity comes in.

public ResponseEntity<UserDto> getUser(...) {
    return ResponseEntity.ok(user);
}

ResponseEntity lets you control:

HTTP Status
Headers
Response Body

Conceptually:

ResponseEntity
      |
      +--- Status
      |
      +--- Headers
      |
      +--- Body

For example:

return ResponseEntity
        .status(HttpStatus.CREATED)
        .body(savedUser);

produces:

HTTP 201 Created

with the user in the response body.


---

11. Why not always use ResponseEntity?

You can, but you don't have to.

This is perfectly reasonable:

@GetMapping
public List<UserDto> getUsers() {
    return userService.findAll();
}

If you simply need:

200 OK
+
response body

you don't necessarily need ResponseEntity.

Use ResponseEntity when you need explicit control over:

status code

headers

body


For example:

return ResponseEntity.status(HttpStatus.CREATED).body(user);

or:

return ResponseEntity.noContent().build();


---

12. HTTP Status Codes You Should Know

For a 1.5 YOE backend interview, know these well:

200 OK

Request succeeded.

Commonly used for:

GET
PUT
PATCH

depending on the operation.


---

201 Created

A new resource was successfully created.

Commonly used for:

POST

Example:

POST /api/users
        ↓
201 Created

It's not that POST must always return 201. The important point is that when the request successfully creates a resource, 201 is the semantically appropriate status.


---

204 No Content

Request succeeded but there is no response body.

Commonly used for:

DELETE

or updates where you intentionally return no body.

Example:

return ResponseEntity.noContent().build();


---

400 Bad Request

The request is invalid.

For example:

Invalid JSON
Invalid input
Validation failure


---

401 Unauthorized

The request lacks valid authentication credentials.

Think:

"Who are you?"


---

403 Forbidden

The user is authenticated but isn't allowed to perform the operation.

Think:

"I know who you are,
but you aren't allowed to do this."


---

404 Not Found

Requested resource doesn't exist.

Example:

GET /api/users/9999

when user 9999 doesn't exist.


---

409 Conflict

The request conflicts with the current state of the resource.

Common examples include duplicate resources or conflicting operations.


---

500 Internal Server Error

Unexpected server-side failure.


---

13. POST: Why 201 Created?

Suppose:

POST /api/users

with:

{
  "name": "Avi"
}

and the server creates:

User ID = 101

The response can be:

HTTP 201 Created

because a new resource was created.

A REST API may also return a Location header indicating the URI of the newly created resource:

Location: /api/users/101

For a 1.5 YOE interview, the important answer is:

> When POST successfully creates a new resource, 201 Created is the semantically appropriate status code. A Location header can be used to identify the newly created resource.



Don't say:

> "POST always returns 201."



That's too absolute.


---

14. Class-Level + Method-Level Mapping

Yes, they combine.

@RequestMapping("/api/users")
public class UserController {

    @GetMapping("/{id}")
    public UserDto getUser(...) {
    }
}

The final path is:

/api/users/{id}

So:

GET /api/users/5

hits the method.

Similarly:

@PostMapping

becomes:

POST /api/users

And:

@GetMapping

becomes:

GET /api/users


---

15. @RequestMapping vs @GetMapping

@RequestMapping is more general.

You can write:

@RequestMapping(
    value = "/users",
    method = RequestMethod.GET
)

But Spring provides shortcut annotations:

@GetMapping("/users")

Similarly:

@PostMapping
@PutMapping
@PatchMapping
@DeleteMapping

are specialized forms of request mapping.

For modern Spring Boot code, you'll commonly use the specialized annotations.


---

16. The Three Most Important Request Annotations

This is worth memorizing:

@PathVariable
      ↓
value from URL PATH

@RequestParam
      ↓
value from QUERY STRING

@RequestBody
      ↓
value from REQUEST BODY

Example:

GET /api/users/10?active=true
                   |
                   +-- @RequestParam

             10
             |
             +-- @PathVariable

For POST:

POST /api/users
Content-Type: application/json

{
    "name": "Avi"
}

JSON
 ↓
@RequestBody
 ↓
UserDto


---

17. Interview Questions

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




---

18. What you should actually remember for your 1.5 YOE interview

Don't memorize the entire section word-for-word. Your mental model should be:

HTTP Request
     ↓
Controller
     ↓
Mapping determines which method handles it
     ↓
+-----------------------------+
|                             |
@PathVariable             @RequestParam
|                             |
URL path                  Query string
|
/users/10                 ?name=avi
|
+-----------------------------+
              |
              ↓
          @RequestBody
              |
              ↓
       JSON → Java object
              |
              ↓
         Service layer
              |
              ↓
       Controller response
              |
              ↓
        ResponseEntity
              |
       +------+------+
       |             |
     Status         Body
       |
  200 / 201 / 204

The one-liner to remember:

> A REST controller receives HTTP requests, mapping annotations determine which method handles the request, request annotations extract data from the path/query/body, and the controller returns an HTTP response—optionally using ResponseEntity to control its status, headers, and body.



This is enough for this topic at 1.5 YOE. The next level would be exception handling, validation, DTOs, global @ControllerAdvice, pagination, and API design—but those should be learned as separate topics rather than cramming them into REST mappings.
