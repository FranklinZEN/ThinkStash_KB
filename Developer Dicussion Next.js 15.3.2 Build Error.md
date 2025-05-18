

Thanks\! I’ll now investigate whether other developers using the default Webpack build in Next.js 15.3.2 have encountered the same ParamCheck RouteContext type error in catch-all API routes. I’ll search GitHub issues, forums, and community discussions to gather insights, potential workarounds, or confirmation of a framework-level bug. I’ll get back to you shortly with the findings.

# **Next.js 15 Catch-All Route Type Error: Reports and Resolutions**

## **Developers Reporting the Build Error**

Numerous developers have encountered a TypeScript build error after upgrading to Next.js 15, especially with dynamic or catch-all API route handlers. The error typically looks like:

*"Type '{ ... params: { **yourParam**: string; } ... }' does not satisfy the constraint 'ParamCheck'"* – often indicating that the `params` object is **“missing** Promise properties like `then`, `catch`, etc..

This has been reported for routes such as `app/api/[id]/route.ts` or catch-all routes (`app/api/[...path]/route.ts`). For example, one catch-all route in a Next 15 app produced: *Expected "Promise", got "Promise\<{ path: string\[\]; }\> | { path: string\[\]; }"*. In all cases, the build fails during type checking, even though the code ran fine in development.

## **Cause: Next.js 15 Treats `params` as a Promise**

This error stems from a **breaking change in Next.js 15**. In Next 15, all route parameters (`params`) and page `searchParams` are now provided as **Promises** rather than plain objects. This was introduced to support asynchronous routes and React 19 features. Essentially, Next.js 15 expects your route handler signature to account for an asynchronous `params`. If your code (written for Next 13/14) defines `context.params` as a normal object, the types no longer match – hence the `ParamCheck<RouteContext>` constraint error.

The Next.js team has **acknowledged** this change and documented it. Official upgrade guides and error docs note that `params` are promise-based in v15, and they even provide a codemod to automatically update your codebase. Maintainers have clarified that this is intentional behavior, not a one-off bug: *“We've indeed switched all `params` and `searchParams` to be promise-based in v15”*. However, many developers initially thought it was a bug, as evidenced by multiple GitHub issues and discussions.

## **GitHub Issues and Community Discussions**

**Multiple issues were filed** on the Next.js repo about this type error. For example, Issue **\#74127** reported that a simple route handler like `export async function PATCH(request, { params: { id: string } })` would fail the build with *“Type `{ params: { id: string; } }` is not a valid type for the function's second argument.”*. Another early issue (**\#72525**) was opened during migration from Next 14 to 15 specifically about the `ParamCheck<RouteContext>` error.

These issues confirm that the problem occurs in the **default Webpack build** (which runs full type-checking on `next build`). In development, many were using Turbopack or saw no error until the production build step. (In fact, some noted that `next dev` ran fine, but `next build` threw the type errors – because the strict type validation happens at build time.)

**Community forums** lit up with developers hitting this. On Stack Overflow, several questions were asked about the `"invalid ... export"` or `ParamCheck` errors. The consensus was that Next 15 expects an async signature. One high-scoring answer explains: *“In Next.js 15, `params` is actually a Promise that needs to be awaited.”* and shows how to fix the function signature. Similarly, a Reddit thread shows a user resolving the issue by changing their route function to accept `params: Promise<...>` and then awaiting it internally.

## **Workarounds and Solutions**

**The primary workaround** (and the official recommendation) is to update your route handler definitions to match the new types. In practice, that means:

**Typing `params` as a Promise:** Change your function signature to something like:

 export async function GET(  
  request: NextRequest,   
  { params }: { params: Promise\<{ id: string }\> }  
) {  
    const id \= await params;  // then use id.id if needed  
    // ... rest of logic ...  
}

*  For a catch-all route, if `params` should be an array (e.g. `{ path: string[] }`), type it as `Promise<{ path: string[] }>`. The key is that the **entire** `params` object is wrapped in a Promise, which you then `await` before accessing its fields. This satisfies Next.js 15's `ParamCheck` constraints.

* **Run the Codemod:** Next.js 15 provides an upgrade codemod that automatically transforms your route and page files to the new async format. Running `npx @next/codemod@latest upgrade` will attempt to adjust your `app` directory code (e.g. making page components `async` and updating `params` usage). Many devs reported that the codemod works for most cases, though some manual fixes might still be needed (especially if the codemod missed certain patterns).

* **Disable strict checking (not ideal):** A few developers temporarily used `@ts-ignore` or loosened types to get builds passing, but this is not recommended. It’s better to properly type the context as above. There is no Next.js config flag to revert to old behavior; the change is by design.

With the above adjustments, the build errors disappear. For instance, after updating their `route.ts` files, developers confirmed the error was resolved and builds succeeded.

## **Next.js Team Response and Issue Status**

From Vercel’s perspective, this is a **known and expected change** rather than an accidental bug. The team’s response (via Next.js maintainer comments and docs) has been to guide users to update their code. They explicitly note that any outdated examples in documentation should be reported so they can be corrected to use async params. In short, Next.js 15 *requires* this new approach, and the official stance is to adapt code accordingly.

That said, the flurry of issues and discussions has been acknowledged. The fact that so many encountered it indicates the developer experience wasn’t entirely smooth. One GitHub issue concluded that the build error *“was likely caused by a bug or incompatibility within Next.js v15 ... related to TypeScript type generation for dynamic routes”*. In at least one case, users downgraded back to Next 14 to unblock their builds. The Next.js team has tracked these reports – for example, the issue about route handler types (\#74127) was marked as a bug initially and then closed once the docs/codemod were in place. Another open issue (\#77609) is still being monitored for any lingering edge cases with dynamic route types in v15.

**In summary**, if you’re using Next 15.3.x (with the default Webpack build) and see the `ParamCheck<RouteContext>` type error on a catch-all or dynamic API route, you are not alone – many others hit the same problem. It is **recognized** in the community and by the Next.js maintainers. The solution is to update your route definitions to the new asynchronous `params` format. All evidence (StackOverflow answers, GitHub discussions, and official Vercel docs) confirms that this is the intended path forward. The issue is being tracked in the Next.js repo, but since it’s a deliberate framework change, the “fix” is essentially to apply the migration. Developers can refer to the Next.js 15 upgrade guide and use the codemod for a smoother transition. Meanwhile, any truly *unexpected* bugs around this (if, say, the types still misbehave after updating) are being addressed in ongoing updates and will be noted in the Next.js release notes or issue tracker.

**Sources:** Community Q\&A and Next.js issue reports detailing the error and resolution; official Next.js documentation and maintainer comments explaining the new `params` behavior and codemod; and Stack Overflow/Reddit solutions confirming the workaround of treating `params` as a promise in route handlers.

