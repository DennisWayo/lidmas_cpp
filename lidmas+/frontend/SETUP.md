# LiDMaS+ Frontend - Open-Source Research Setup

## Adapter Sessions (Current Runtime Flow)

Recommended frontend launch:

```bash
cd "lidmas+/frontend"
npm install
VITE_API_BASE_URL=http://127.0.0.1:8080/api/v1 npm run dev
```

The frontend targets the backend service configured by `VITE_API_BASE_URL`.

Authentication:

- UI now enforces backend sign-in/sign-up before opening workspace.
- Protected API calls use bearer token issued by backend (`/api/v1/auth/signin` or `/api/v1/auth/signup`).

The Jobs page includes an `Adapter Sessions` control surface for launching provider flows:

- IBM live superconducting telemetry
- Ankaa superconducting replay
- Xanadu remote GKP replay (SSH)

Launcher behavior:

- Operator chooses provider family first (`IBM`, `Ankaa`, `Xanadu`)
- Frontend maps provider family to adapter id automatically
- If no run is selected, frontend auto-creates provider/run before launch

Backend requirement:

- `/api/v1/integrations/sessions` endpoints must be available from the backend configured in `VITE_API_BASE_URL`.

Quick check:

```bash
curl -i http://127.0.0.1:8080/api/v1/integrations/sessions
```

If this returns `404`, the frontend is connected to an older backend build.

## Architecture Overview

This frontend uses a modern open-source research UI stack:

### Core Dependencies
- **React 18** - UI framework
- **React Router v6** - Client-side routing
- **TypeScript** - Type safety
- **Vite** - Build tool & dev server
- **TanStack Query** - Server state management

### UI & Styling
- **Tailwind CSS v4** - Utility-first CSS framework
- **Shadcn/ui components** - Pre-built, accessible React components
- **Lucide React** - Beautiful icon library
- **CVA (class-variance-authority)** - Component variant management

### Forms & Data
- **React Hook Form** - Lightweight form state management
- **Recharts** - Data visualization & charts (for telemetry, analysis)
- **Zustand** - Simple state management (alternative to Redux)

## File Structure

```
frontend/
├── src/
│   ├── components/
│   │   └── ui/               # Shadcn/ui components (Button, Card, Input, etc.)
│   ├── lib/
│   │   └── utils.ts          # Utility functions (cn helper for Tailwind)
│   ├── ui/                   # Page components (AppShell, DashboardPage, etc.)
│   ├── api/                  # API client & hooks
│   ├── router/               # Route definitions
│   ├── styles.css            # Global styles (includes Tailwind directives)
│   └── main.tsx              # App entry point
├── tailwind.config.ts        # Tailwind configuration
├── postcss.config.js         # PostCSS plugins
├── vite.config.ts            # Vite configuration with path alias (@)
└── tsconfig.json             # TypeScript config with @ path alias
```

## Key Features

### 1. Path Alias (@)
Import files using `@` instead of relative paths:
```typescript
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
```

### 2. Tailwind CSS Integration
- Uses **HSL CSS variables** for color theming
- Maintains **backward compatibility** with existing design tokens
- Supports **dark mode** (can be extended in tailwind.config.ts)

### 3. Component Library
Pre-built components in `src/components/ui/`:
- `Button` - Variants: default, destructive, outline, secondary, ghost, link
- `Card` - CardHeader, CardContent, CardFooter, CardTitle, CardDescription
- `Input` - Text input with focus states
- `Select` - Dropdown with Tailwind styling
- `Badge` - Inline status badges with variants
- `Table` - Full-featured data table components

### 4. Accessible Components
All components follow WAI-ARIA standards with:
- Keyboard navigation support
- Focus management
- Screen reader compatible

## Development Workflow

### Starting the dev server:
```bash
npm run dev          # or
npm run lidmas       # Opens in Chrome automatically
```

### Building for production:
```bash
npm run build        # Builds to dist/
npm run preview      # Preview production build locally
```

### TypeScript checking:
```bash
npm run build        # Includes `tsc --noEmit` type checking
```

## Migrating Existing Components

### From custom CSS to Shadcn/ui + Tailwind:

**Before (Custom CSS):**
```tsx
<div className="panel panel-blue">
  <h3>Title</h3>
  <p className="muted">Subtitle</p>
</div>
```

**After (Tailwind + Shadcn):**
```tsx
import { Card, CardTitle, CardDescription } from "@/components/ui/card"

<Card>
  <CardTitle>Title</CardTitle>
  <CardDescription>Subtitle</CardDescription>
</Card>
```

### Using Tailwind Classes:
```tsx
<button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
  Click me
</button>

// Or using our Button component
import { Button } from "@/components/ui/button"
<Button variant="default">Click me</Button>
```

## Color System

### CSS Variables (defined in styles.css)
```css
--primary: 210 100% 50%;      /* Blue */
--secondary: 120 100% 35%;    /* Green */
--destructive: 0 84% 60%;     /* Red */
--accent: 36 100% 50%;        /* Orange */
--muted: 210 10% 35%;         /* Gray */
```

### Usage in Tailwind:
```html
<!-- Uses Tailwind's color system -->
<div className="bg-primary text-primary-foreground">Primary</div>
<div className="bg-destructive text-destructive-foreground">Destructive</div>
```

## Adding New Components

Create a new component in `src/components/ui/example.tsx`:
```typescript
import * as React from "react"
import { cn } from "@/lib/utils"

const Example = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("p-4 rounded-lg border", className)}
      {...props}
    />
  )
)
Example.displayName = "Example"

export { Example }
```

Then export from `src/components/ui/index.ts`:
```typescript
export { Example } from "./example"
```

## Form Handling with React Hook Form

```typescript
import { useForm } from "react-hook-form"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export function MyForm() {
  const { register, handleSubmit } = useForm()

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <Input {...register("email")} placeholder="Email" />
      <Button type="submit">Submit</Button>
    </form>
  )
}
```

## Data Visualization with Recharts

For your telemetry, analysis, and dashboard pages:
```typescript
import { LineChart, Line, XAxis, YAxis, CartesianGrid } from "recharts"

const data = [{ time: "00:00", value: 100 }, { time: "01:00", value: 120 }]

export function Chart() {
  return (
    <LineChart width={400} height={300} data={data}>
      <CartesianGrid />
      <XAxis dataKey="time" />
      <YAxis />
      <Line type="monotone" dataKey="value" stroke="#2a6fd0" />
    </LineChart>
  )
}
```

## Next Steps

1. **Create example pages** - Convert one dashboard page to use new components
2. **Add icons** - Import from `lucide-react` for consistent iconography
3. **Form pages** - Update Settings/Conformance pages with React Hook Form
4. **Charts** - Add Recharts visualizations to Telemetry/Analysis pages
5. **State management** - Consider Zustand for complex state

## Debugging

### Tailwind classes not working?
1. Check that `src/styles.css` is imported in `src/main.tsx`
2. Verify class names are correct (Tailwind only generates classes in content paths)
3. Check `tailwind.config.ts` includes your file paths

### Component not found?
1. Make sure it's exported from `src/components/ui/index.ts`
2. Check the import path uses `@/` alias

### TypeScript errors?
1. Run `npm run build` to see type errors
2. Check `tsconfig.json` paths configuration
