// The guided demo: what to click, in order. Each step says which page it lives on,
// what to point at, and (optionally) how to tell the visitor has done it, so the
// tour moves on by itself. Targets are found in the page by role/label/text, so
// the tour needs no hooks inside the app's components.

export type Step = {
  id: string;
  /** Pages this step belongs to. */
  path: RegExp;
  title: string;
  text: string;
  /** Short instruction shown in an accent box. */
  action?: string;
  target?: () => Element | null;
  /** True once the visitor has done the thing: the tour advances by itself. */
  done?: () => boolean;
  /** The step needs this on screen (e.g. the explorer, not the "limited preview" notice). */
  requires?: () => boolean;
  /** Where to send someone who is on the wrong page for this step. */
  fallbackHref?: string;
  fallbackLabel?: string;
};

const $ = (selector: string) => document.querySelector(selector);
const byText = (selector: string, pattern: RegExp) =>
  Array.from(document.querySelectorAll(selector)).find((el) => pattern.test((el.textContent ?? "").trim())) ?? null;
const path = () => window.location.pathname;
const aside = () => $('aside[aria-label="Explanations and results"]');
const hasText = (el: Element | null, text: string) => !!el && (el.textContent ?? "").includes(text);
const explorer = () => !!$('section[aria-label="Timeline"]');
const BARNARD = "/explore?q=Barnard%27s%20Star&ra=269.4463&dec=4.7682&fov=0.2";

export const STEPS: Step[] = [
  {
    id: "welcome",
    path: /^\/$/,
    title: "Welcome to Hiraya",
    text: "A two-minute guided demo. You’ll look at the infrared sky, watch a star move, find something nobody has listed, and share it. Everything runs in your browser.",
  },
  {
    id: "search",
    path: /^\/$/,
    title: "Search the sky",
    text: "The map is the real sky: drag it, zoom it, try the search. Deep exploration is open for one region in this preview, Barnard’s Star. Other objects explain that and offer a button.",
    action: "Type “barnard” in the search and press Enter.",
    target: () => $('input[aria-label^="Search the sky"]'),
    done: () => path().startsWith("/explore"),
  },
  {
    id: "timeline",
    path: /^\/explore/,
    title: "Twelve visits over 15 months",
    text: "SPHEREx looked at this patch again and again. Each dot is one visit. The grid stays fixed to the sky, so anything that moves slides across the squares.",
    action: "Press Play, or click the first dot then the last, and watch the bright star drift.",
    target: () => $('section[aria-label="Timeline"]'),
    requires: explorer,
    fallbackHref: BARNARD,
    fallbackLabel: "Open the Barnard’s Star region",
  },
  {
    id: "select",
    path: /^\/explore/,
    title: "Select something",
    text: "Switch to Select box and drag around the bright star in the middle of the map.",
    action: "Click Select box, then drag a box around the star.",
    target: () => byText("button", /^Select box$/),
    done: () => !!aside()?.querySelector("footer button"),
    requires: explorer,
    fallbackHref: BARNARD,
    fallbackLabel: "Open the Barnard’s Star region",
  },
  {
    id: "read",
    path: /^\/explore/,
    title: "What is inside the box?",
    text: "Hiraya guesses what you selected, here a cool red star, and plots its spectrum: brightness at each infrared colour. Dips are fingerprints of molecules such as water vapour.",
    target: aside,
    requires: explorer,
  },
  {
    id: "verify",
    path: /^\/explore/,
    title: "Is it already known?",
    text: "Verify checks the selection against catalogues of stars, asteroids and detector glitches.",
    action: "Click “Verify: is it already known?”",
    target: () => aside()?.querySelector("footer button") ?? null,
    done: () => !!byText("aside button", /^Back$/),
    requires: explorer,
  },
  {
    id: "known",
    path: /^\/explore/,
    title: "A known star",
    text: "It’s Barnard’s Star, the fastest-moving star in our sky: 10 arcseconds every year. Known objects earn points. Now let’s look for something nobody listed.",
    action: "Click Back, then continue.",
    target: aside,
    requires: explorer,
  },
  {
    id: "analyze",
    path: /^\/explore/,
    title: "Find everything that moved",
    text: "Analyze motion compares all twelve visits and lists what shifted between them.",
    action: "Click “Analyze motion” in the timeline bar.",
    target: () => byText('section[aria-label="Timeline"] button', /Analyze/),
    done: () => !!$('[aria-label="Movers found"]'),
    requires: explorer,
  },
  {
    id: "movers",
    path: /^\/explore/,
    title: "Two movers",
    text: "Mover 1 is Barnard’s Star again. Mover 2 is faint and slides toward the lower left, and it’s the interesting one. Hiraya’s guess for it: a cold brown dwarf, an object between a planet and a star.",
    action: "Click mover 2 in the list.",
    target: () => $('[aria-label="Movers found"]'),
    requires: explorer,
  },
  {
    id: "verify-mover",
    path: /^\/explore/,
    title: "Check the mystery mover",
    text: "Run Verify on mover 2. Nothing in the catalogues matches it. That makes it a lead worth asking others about, not a discovery.",
    action: "Click Verify and wait a couple of seconds.",
    target: () => aside()?.querySelector("footer button") ?? aside(),
    done: () => hasText(aside(), "match this to anything"),
    requires: explorer,
  },
  {
    id: "discuss",
    path: /^\/explore/,
    title: "Share it",
    text: "Post it for others to check. Hiraya attaches a snapshot, a blink animation and the spectrum for you.",
    action: "Click “Discuss suspected motion”.",
    target: () => byText("aside button", /^Discuss suspected motion$/),
    done: () => path() === "/share",
    requires: explorer,
  },
  {
    id: "compose",
    path: /^\/share/,
    title: "Write a short note",
    text: "Give it a title and say what you saw. No time? “Use an example” fills it in. Posts are saved in your browser only; nothing is uploaded.",
    action: "Click “Create discussion post”.",
    target: () => $("main form"),
    done: () => path().startsWith("/findings/"),
    fallbackHref: "/explore",
    fallbackLabel: "Back to Explore",
  },
  {
    id: "post",
    path: /^\/findings\//,
    title: "Your post is live",
    text: "The snapshot, the blink animation of all the visits and the brightness spectrum are attached. The ring follows the object as it moves.",
    action: "Click “Blink” to play the animation.",
    target: () => $("figure"),
  },
  {
    id: "discussions",
    path: /^\/findings\//,
    title: "Everyone’s discussions",
    text: "Posts from the community live together on one page.",
    action: "Click “All discussions”.",
    target: () => byText("a", /All discussions/),
    done: () => path() === "/discussions",
  },
  {
    id: "end",
    path: /^\/discussions/,
    title: "That’s the loop",
    text: "Explore, check, and share. Spot something, verify it, and put it in front of others. Thanks for trying Hiraya!",
  },
];
