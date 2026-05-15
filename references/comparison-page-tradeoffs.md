# Comparison page — layout tradeoffs and CSS pitfalls

The comparison page is the deliverable. If it's awkward to use, the user can't make a decision and the whole skill fails. This doc captures what we learned from real sessions so future agents pick the right layout the first time.

## Layouts considered

| Layout | When to use | When NOT to use | Real-user feedback |
|---|---|---|---|
| Grid (NN iframes side-by-side at 720px height) | First-look comparison of 3-5 variants of similar density | When variants are dense / text-heavy and need >800px height | Worked for early eval; got cluttered at 5+ variants |
| Theatre (one large preview + thumbnail strip) | Single-focus deep dive after user has narrowed to ~2 finalists | When the user wants to compare; click-and-wait kills comparison | User feedback (paraphrased): "bad experience — worse than just a list page" — got rejected |
| Sidebar+Scroll (left TOC, right scrollable feed of full-height variants) ★ DEFAULT | Any time you have 3-7 variants of any density and need both list-overview + full-detail | Only on very small screens (<700px wide) — falls back to top dropdown | Currently in use, working |

## Why Sidebar+Scroll won

It's both a list AND a feed. The sidebar serves the "where am I in the set" overview need — the user can see all N variants by name without scrolling, click to jump, and the active item highlights as they scroll. The right pane is a scrollable feed where each variant gets its full natural height, inline, no click-to-load delay.

This matters because comparison is a *side-by-side cognitive task*. The Theatre layout broke comparison: clicking thumbnail → waiting for iframe → forgetting what the previous one looked like. Sidebar+Scroll keeps the previous variant one swipe of the wheel away. The user's eyes do the comparing, not their short-term memory.

Auto-highlight on scroll provides the "where am I" affordance that grids lack. In a 5-iframe grid, when the user is deep in the third variant they have no marker telling them which one they're looking at; in Sidebar+Scroll the active sidebar item answers that for free.

Keyboard nav (j/k or ↑/↓ to jump between variants) makes power users fast. The whole point of the comparison is rapid A/B/C — anything that adds clicks is friction.

## Known CSS pitfalls (do not repeat)

Each pitfall below is something we shipped, broke, and had to fix mid-session. Copy the corrected pattern; don't re-derive.

- **Pitfall 1 — flex-derived iframe height collapses to 0.** Pattern that broke: parent had `display: flex; flex-direction: column`, iframe wrapper had `flex: 1; min-height: 100vh`, iframe inside had `height: 100%`. Result: iframe rendered at 0px and the user reported "the content inside is invisible / it didn't expand". **Fix**: give the iframe container an explicit height like `calc(100vh - 110px)` with a `min-height: 600px` fallback. Don't rely on flex to derive iframe size — iframes don't participate in flex sizing the way divs do.

- **Pitfall 2 — scroll-snap locks at unexpected offsets.** Pattern that broke: `scroll-snap-type: y proximity` on the scrolling container with each variant section as `min-height: 100vh; scroll-snap-align: start`. Result: scrolling between variants felt sticky and could lock the viewport mid-variant, giving a "content cut off" appearance. **Fix**: don't use scroll-snap for landing-page comparison. Plain scroll plus `scroll-margin-top: 80px` on each section (so click-to-jump from sidebar lands below any sticky header) is enough.

- **Pitfall 3 — lazy-loading the first iframe.** Pattern that broke: every iframe got `loading="lazy"`, including the topmost one. Some browsers don't trigger the load fast enough on initial paint, and the page looked empty for 1-2 seconds, which reads as broken. **Fix**: eager-load the first 1-2 iframes (`loading="eager"` or omit the attribute), lazy-load the rest. The user always sees content immediately; the rest streams in as they scroll.

- **Pitfall 4 — transform: scale() for thumbnails.** Pattern that broke: thumbnail strip in the sidebar rendered each variant as `<iframe>` with `transform: scale(0.2)`. Result: every iframe still loaded the full page (so 5 full page loads upfront), the scaled iframe blurred badly, and layout costs spiked. **Fix**: if you really need thumbnails, generate static screenshots as a build step (out-of-scope for v1). Otherwise just don't — text labels in the sidebar are fine and load instantly.

## Decision tree for picking a layout in the future

By variant count:

```
N variants to compare?
  ├─ N ≤ 2 → Side-by-side split-screen (special case, not a normal mode)
  ├─ 3 ≤ N ≤ 7 → Sidebar+Scroll (default, what we use)
  ├─ 8 ≤ N ≤ 15 → Sidebar+Scroll with grouped sidebar headers
  └─ N > 15 → Stop and ask user to narrow first; don't generate this many
```

By variant character:

```
Variants are mostly visually identical (small CSS differences only)?
  → Maybe Theatre — user can switch quickly to A/B specific elements
Variants are highly distinct directions?
  → Definitely Sidebar+Scroll — full-page context matters
```

When in doubt, default to Sidebar+Scroll. It's the only layout that hasn't been rejected by a user yet.
