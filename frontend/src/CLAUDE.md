## Angular code rules

- always use Signal Forms. Don't use reactive or model-driven forms.

- don't use Rxjs and Observables unless explicitly told to. Define the API of your service layers with Promises.

- For handling async code, prefer Promises and the async /await syntax

- If you run into Angular APIs that are still Observable-based, convert them to Promises using firstValueFrom

- where applicable, keep a common CSS theme in shared files that you import/apply to the components,
  to make it easy to adapt the theme in the future.

- all HTTP requests target the backend by having the url start with /api.

- don't use inline HTML templates or CSS in Angular components. Always use external files.
