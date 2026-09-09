import {
  MODEL_QUERY_PARAM,
  defaultVisibleModels,
  resolveSelectedModels,
  sameModelSet,
  serializeModelsParam,
} from "./models";

function availableFromDom(): string[] {
  const toggles = document.querySelectorAll<HTMLInputElement>("[data-model-toggle]");
  if (toggles.length > 0) {
    return [...toggles].map((el) => el.value);
  }
  return [
    ...new Set(
      [...document.querySelectorAll<HTMLElement>("[data-model]")].map((el) => el.dataset.model ?? ""),
    ),
  ].filter(Boolean);
}

function applyVisibility(selected: Set<string>): void {
  for (const el of document.querySelectorAll<HTMLElement>("[data-model]")) {
    const model = el.dataset.model ?? "";
    if (selected.has(model)) el.setAttribute("data-show", "");
    else el.removeAttribute("data-show");
  }

  for (const group of document.querySelectorAll<HTMLElement>("[data-model-group]")) {
    const anyVisible = [...group.querySelectorAll<HTMLElement>("[data-model]")].some((el) =>
      el.hasAttribute("data-show"),
    );
    const empty = group.querySelector<HTMLElement>("[data-model-group-empty]");
    if (empty) empty.hidden = anyVisible;
  }

  for (const el of document.querySelectorAll<HTMLElement>("[data-model-visible-count]")) {
    const total = Number(el.dataset.modelTotal ?? "0");
    const visible = document.querySelectorAll(".model-run[data-model][data-show]").length;
    if (selected.size === 0) {
      el.textContent = "No models selected";
    } else if (visible === total) {
      el.textContent = `${total} model${total === 1 ? "" : "s"} played this puzzle`;
    } else {
      el.textContent = `Showing ${visible} of ${total} models`;
    }
  }
}

function syncCheckboxes(selected: Set<string>): void {
  for (const input of document.querySelectorAll<HTMLInputElement>("[data-model-toggle]")) {
    input.checked = selected.has(input.value);
  }
}

function writeUrl(selected: string[], available: string[]): void {
  const url = new URL(window.location.href);
  const defaults = defaultVisibleModels(available);
  if (sameModelSet(selected, defaults)) {
    url.searchParams.delete(MODEL_QUERY_PARAM);
  } else {
    url.searchParams.set(MODEL_QUERY_PARAM, serializeModelsParam(selected));
  }
  history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

function preserveModelsOnLinks(selected: string[], available: string[]): void {
  const defaults = defaultVisibleModels(available);
  const useDefault = sameModelSet(selected, defaults);
  const paramValue = serializeModelsParam(selected);

  for (const anchor of document.querySelectorAll<HTMLAnchorElement>("a[href]")) {
    const href = anchor.getAttribute("href");
    if (!href || href.startsWith("#") || href.startsWith("mailto:") || /^https?:/i.test(href)) {
      continue;
    }

    let url: URL;
    try {
      url = new URL(href, window.location.origin);
    } catch {
      continue;
    }
    if (url.origin !== window.location.origin) continue;

    if (useDefault) url.searchParams.delete(MODEL_QUERY_PARAM);
    else url.searchParams.set(MODEL_QUERY_PARAM, paramValue);

    anchor.setAttribute("href", `${url.pathname}${url.search}${url.hash}`);
  }
}

function readSelection(available: string[]): string[] {
  return resolveSelectedModels(window.location.search, available);
}

function syncSummary(selected: string[]): void {
  const el = document.querySelector<HTMLElement>("[data-model-filter-summary]");
  if (!el) return;
  const n = selected.length;
  el.textContent = n === 0 ? "None selected" : `${n} selected`;
}

function apply(selected: string[], available: string[]): void {
  const set = new Set(selected);
  syncCheckboxes(set);
  applyVisibility(set);
  writeUrl(selected, available);
  preserveModelsOnLinks(selected, available);
  syncSummary(selected);

  const hint = document.querySelector<HTMLElement>("[data-model-filter-hint]");
  if (hint) hint.hidden = selected.length > 0;
}

export function initModelFilter(): void {
  const available = availableFromDom();
  if (available.length === 0) return;

  apply(readSelection(available), available);

  document.querySelector("[data-model-filter]")?.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement) || !target.hasAttribute("data-model-toggle")) {
      return;
    }
    const next = [...document.querySelectorAll<HTMLInputElement>("[data-model-toggle]:checked")].map(
      (el) => el.value,
    );
    apply(next, available);
  });

  window.addEventListener("popstate", () => {
    apply(readSelection(available), available);
  });
}
