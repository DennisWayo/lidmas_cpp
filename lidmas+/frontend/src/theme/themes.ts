export type ThemeId =
  | "dark-core"
  | "light-core"
  | "system-auto"
  | "gerry-noctis"
  | "gerry-lagoon"
  | "gerry-ember"
  | "gerry-sage"
  | "gerry-parchment";

interface ThemePalette {
  bg: string;
  bgSecondary: string;
  bgTertiary: string;
  line: string;
  text: string;
  textSecondary: string;
  textMuted: string;
  blue: string;
  blueHover: string;
  green: string;
  orange: string;
  red: string;
  colorScheme: "dark" | "light";
}

interface ThemeDefinition {
  id: Exclude<ThemeId, "system-auto">;
  label: string;
  family: "core" | "gerry";
  description: string;
  palette: ThemePalette;
}

export interface ThemeOption {
  id: ThemeId;
  label: string;
  family: "core" | "gerry" | "auto";
  description: string;
}

export interface ThemeSwatch {
  bg: string;
  accent: string;
  text: string;
}

export const THEME_STORAGE_KEY = "lidmas.ui.theme";

const THEMES: Record<Exclude<ThemeId, "system-auto">, ThemeDefinition> = {
  "dark-core": {
    id: "dark-core",
    label: "Core Dark",
    family: "core",
    description: "Default dark operations theme.",
    palette: {
      bg: "#000000",
      bgSecondary: "#080808",
      bgTertiary: "#101010",
      line: "#1f1f1f",
      text: "#f3f4f6",
      textSecondary: "#c4cad4",
      textMuted: "#818b99",
      blue: "#3f89ea",
      blueHover: "#2f6fc4",
      green: "#26b36b",
      orange: "#f0982f",
      red: "#e25564",
      colorScheme: "dark",
    },
  },
  "light-core": {
    id: "light-core",
    label: "Core Light",
    family: "core",
    description: "Neutral light workspace theme.",
    palette: {
      bg: "#f5f7fa",
      bgSecondary: "#ffffff",
      bgTertiary: "#f0f3f8",
      line: "#d6dce8",
      text: "#1a2334",
      textSecondary: "#33415c",
      textMuted: "#5b6b88",
      blue: "#2f6fcd",
      blueHover: "#2559a6",
      green: "#198f58",
      orange: "#cc7a1f",
      red: "#c43f52",
      colorScheme: "light",
    },
  },
  "gerry-noctis": {
    id: "gerry-noctis",
    label: "Gerry Noctis",
    family: "gerry",
    description: "Deep navy with high-contrast telemetry accents.",
    palette: {
      bg: "#060914",
      bgSecondary: "#0d1224",
      bgTertiary: "#131b33",
      line: "#263153",
      text: "#ecf1ff",
      textSecondary: "#b7c3e8",
      textMuted: "#7f8ebb",
      blue: "#59a3ff",
      blueHover: "#3f89ea",
      green: "#41d18d",
      orange: "#f4b15e",
      red: "#ff7078",
      colorScheme: "dark",
    },
  },
  "gerry-lagoon": {
    id: "gerry-lagoon",
    label: "Gerry Lagoon",
    family: "gerry",
    description: "Cool teal-operational palette for long monitoring sessions.",
    palette: {
      bg: "#041318",
      bgSecondary: "#0b1e26",
      bgTertiary: "#112a34",
      line: "#1f404e",
      text: "#e9fbff",
      textSecondary: "#b4dce5",
      textMuted: "#75a2ad",
      blue: "#56c5e7",
      blueHover: "#39a7cc",
      green: "#45d88f",
      orange: "#ffb561",
      red: "#ff7f82",
      colorScheme: "dark",
    },
  },
  "gerry-ember": {
    id: "gerry-ember",
    label: "Gerry Ember",
    family: "gerry",
    description: "Graphite background with warm amber interaction tone.",
    palette: {
      bg: "#121111",
      bgSecondary: "#1b1716",
      bgTertiary: "#251f1d",
      line: "#3a2f2b",
      text: "#f8f0eb",
      textSecondary: "#d7c4b7",
      textMuted: "#a79186",
      blue: "#ff9a4c",
      blueHover: "#e47f2d",
      green: "#6bd48f",
      orange: "#ffbf66",
      red: "#f56f6f",
      colorScheme: "dark",
    },
  },
  "gerry-sage": {
    id: "gerry-sage",
    label: "Gerry Sage",
    family: "gerry",
    description: "Muted evergreen theme tuned for reduced eye strain.",
    palette: {
      bg: "#08110d",
      bgSecondary: "#101c17",
      bgTertiary: "#172720",
      line: "#2b4237",
      text: "#e9f5ee",
      textSecondary: "#b8d5c4",
      textMuted: "#87aa97",
      blue: "#7ec49d",
      blueHover: "#5cae84",
      green: "#5ecb80",
      orange: "#e8bb64",
      red: "#ef7d78",
      colorScheme: "dark",
    },
  },
  "gerry-parchment": {
    id: "gerry-parchment",
    label: "Gerry Parchment",
    family: "gerry",
    description: "Soft paper-like light theme for report review workflows.",
    palette: {
      bg: "#f5f1e8",
      bgSecondary: "#fffaf1",
      bgTertiary: "#efe7d8",
      line: "#d7c8ad",
      text: "#2d2a22",
      textSecondary: "#5a5243",
      textMuted: "#877a63",
      blue: "#4c6f9f",
      blueHover: "#3a5b8a",
      green: "#3f8a5d",
      orange: "#c1863c",
      red: "#b55555",
      colorScheme: "light",
    },
  },
};

export const THEME_OPTIONS: ThemeOption[] = [
  {
    id: "system-auto",
    label: "System Auto",
    family: "auto",
    description: "Follows your OS dark/light preference.",
  },
  ...Object.values(THEMES).map((theme) => ({
    id: theme.id,
    label: theme.label,
    family: theme.family,
    description: theme.description,
  })),
];

export function getThemeSwatch(themeId: ThemeId): ThemeSwatch {
  if (themeId === "system-auto") {
    const resolved = resolveTheme("system-auto");
    return {
      bg: resolved.palette.bgSecondary,
      accent: resolved.palette.blue,
      text: resolved.palette.text,
    };
  }
  const theme = THEMES[themeId];
  return {
    bg: theme.palette.bgSecondary,
    accent: theme.palette.blue,
    text: theme.palette.text,
  };
}

function systemResolvedTheme(): Exclude<ThemeId, "system-auto"> {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return "dark-core";
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark-core" : "light-core";
}

function resolveTheme(themeId: ThemeId): ThemeDefinition {
  const resolvedId = themeId === "system-auto" ? systemResolvedTheme() : themeId;
  return THEMES[resolvedId];
}

function writeCssVariables(palette: ThemePalette): void {
  if (typeof document === "undefined") {
    return;
  }
  const root = document.documentElement;
  root.style.setProperty("--bg", palette.bg);
  root.style.setProperty("--bg-secondary", palette.bgSecondary);
  root.style.setProperty("--bg-tertiary", palette.bgTertiary);
  root.style.setProperty("--line", palette.line);
  root.style.setProperty("--text", palette.text);
  root.style.setProperty("--text-secondary", palette.textSecondary);
  root.style.setProperty("--text-muted", palette.textMuted);
  root.style.setProperty("--blue", palette.blue);
  root.style.setProperty("--blue-hover", palette.blueHover);
  root.style.setProperty("--green", palette.green);
  root.style.setProperty("--orange", palette.orange);
  root.style.setProperty("--red", palette.red);
  root.style.setProperty("color-scheme", palette.colorScheme);
}

export function getStoredThemeId(): ThemeId | null {
  if (typeof window === "undefined") {
    return null;
  }
  const value = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (!value) {
    return null;
  }
  return THEME_OPTIONS.some((option) => option.id === value) ? (value as ThemeId) : null;
}

export function applyTheme(themeId: ThemeId, options?: { persist?: boolean }): void {
  writeCssVariables(resolveTheme(themeId).palette);
  if (typeof document !== "undefined") {
    document.documentElement.dataset.theme = themeId;
  }
  if (options?.persist !== false && typeof window !== "undefined") {
    window.localStorage.setItem(THEME_STORAGE_KEY, themeId);
  }
}

let systemListenerInstalled = false;

function installSystemThemeListener(): void {
  if (systemListenerInstalled || typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return;
  }
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const update = () => {
    if (getStoredThemeId() === "system-auto") {
      applyTheme("system-auto", { persist: false });
    }
  };
  if (typeof media.addEventListener === "function") {
    media.addEventListener("change", update);
  } else if (typeof media.addListener === "function") {
    media.addListener(update);
  }
  systemListenerInstalled = true;
}

export function initializeTheme(): ThemeId {
  const stored = getStoredThemeId() ?? "dark-core";
  applyTheme(stored, { persist: false });
  installSystemThemeListener();
  return stored;
}
