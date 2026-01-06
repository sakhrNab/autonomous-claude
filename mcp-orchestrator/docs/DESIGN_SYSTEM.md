# UI Design System

This document defines the UI design patterns and guidelines for all interfaces built by the Autonomous Operator System.

## Core Principles

1. **Mobile-First**: Design for mobile first, then scale up
2. **Responsive**: All layouts must work on all screen sizes
3. **Accessible**: Follow WCAG 2.1 AA guidelines
4. **Consistent**: Use the same patterns throughout
5. **Dark Mode First**: Default to dark theme

## Color Palette

### Dark Theme (Default)

```css
/* Background colors */
--bg-primary: #0f172a;      /* Main background (slate-900) */
--bg-secondary: #1e293b;    /* Cards, modals (slate-800) */
--bg-tertiary: #334155;     /* Hover states (slate-700) */

/* Text colors */
--text-primary: #f8fafc;    /* Main text (slate-50) */
--text-secondary: #94a3b8;  /* Secondary text (slate-400) */
--text-muted: #64748b;      /* Muted text (slate-500) */

/* Accent colors */
--accent-primary: #3b82f6;  /* Primary actions (blue-500) */
--accent-hover: #2563eb;    /* Primary hover (blue-600) */
--accent-success: #22c55e;  /* Success (green-500) */
--accent-warning: #f59e0b;  /* Warning (amber-500) */
--accent-error: #ef4444;    /* Error (red-500) */

/* Border colors */
--border-default: #334155;  /* Default borders (slate-700) */
--border-focus: #3b82f6;    /* Focus state (blue-500) */
```

### Light Theme

```css
--bg-primary: #ffffff;
--bg-secondary: #f8fafc;
--bg-tertiary: #f1f5f9;
--text-primary: #0f172a;
--text-secondary: #475569;
--text-muted: #94a3b8;
```

## Typography

### Font Stack

```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
font-family-mono: 'SF Mono', 'Fira Code', 'Monaco', 'Consolas', monospace;
```

### Font Sizes (Tailwind)

| Name | Size | Line Height | Usage |
|------|------|-------------|-------|
| xs | 0.75rem (12px) | 1rem | Badges, labels |
| sm | 0.875rem (14px) | 1.25rem | Secondary text, captions |
| base | 1rem (16px) | 1.5rem | Body text |
| lg | 1.125rem (18px) | 1.75rem | Large body text |
| xl | 1.25rem (20px) | 1.75rem | Card titles |
| 2xl | 1.5rem (24px) | 2rem | Section headers |
| 3xl | 1.875rem (30px) | 2.25rem | Page titles |

## Spacing

Use Tailwind spacing scale consistently:

```
p-1: 0.25rem (4px)   - Tight spacing
p-2: 0.5rem (8px)    - Small spacing
p-3: 0.75rem (12px)  - Compact spacing
p-4: 1rem (16px)     - Standard spacing
p-6: 1.5rem (24px)   - Section spacing
p-8: 2rem (32px)     - Large spacing
```

### Standard Patterns

```css
/* Card padding */
.card { padding: 1.5rem; }  /* p-6 */

/* Section spacing */
.section { margin-top: 2rem; margin-bottom: 2rem; }  /* my-8 */

/* Element gaps */
.stack { gap: 1rem; }  /* gap-4 */
.inline { gap: 0.5rem; }  /* gap-2 */
```

## Components

### Buttons

```html
<!-- Primary Button -->
<button class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors">
    Primary Action
</button>

<!-- Secondary Button -->
<button class="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition-colors">
    Secondary
</button>

<!-- Danger Button -->
<button class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors">
    Delete
</button>

<!-- Ghost Button -->
<button class="px-4 py-2 text-slate-300 hover:bg-slate-800 rounded-lg font-medium transition-colors">
    Cancel
</button>
```

### Cards

```html
<div class="bg-slate-800 rounded-xl p-6 shadow-lg border border-slate-700">
    <h3 class="text-xl font-semibold text-white mb-2">Card Title</h3>
    <p class="text-slate-400">Card content goes here</p>
</div>
```

### Inputs

```html
<!-- Text Input -->
<input
    type="text"
    class="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition-colors"
    placeholder="Enter text..."
/>

<!-- Textarea -->
<textarea
    class="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none resize-none transition-colors"
    rows="4"
    placeholder="Enter description..."
></textarea>
```

### Status Badges

```html
<!-- Success -->
<span class="px-2 py-1 text-xs font-medium rounded-full bg-green-900/50 text-green-400">
    Done
</span>

<!-- In Progress -->
<span class="px-2 py-1 text-xs font-medium rounded-full bg-blue-900/50 text-blue-400">
    Running
</span>

<!-- Warning -->
<span class="px-2 py-1 text-xs font-medium rounded-full bg-amber-900/50 text-amber-400">
    Pending
</span>

<!-- Error -->
<span class="px-2 py-1 text-xs font-medium rounded-full bg-red-900/50 text-red-400">
    Failed
</span>
```

### Modals

```html
<div class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
    <div class="bg-slate-800 rounded-xl p-6 max-w-lg w-full mx-4 shadow-2xl border border-slate-700">
        <!-- Header -->
        <div class="flex justify-between items-center mb-4">
            <h2 class="text-xl font-semibold text-white">Modal Title</h2>
            <button class="text-slate-400 hover:text-white">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                </svg>
            </button>
        </div>

        <!-- Content -->
        <div class="text-slate-300 mb-6">
            Modal content here
        </div>

        <!-- Actions -->
        <div class="flex justify-end gap-3">
            <button class="px-4 py-2 text-slate-300 hover:bg-slate-700 rounded-lg">
                Cancel
            </button>
            <button class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg">
                Confirm
            </button>
        </div>
    </div>
</div>
```

### Loading States

```html
<!-- Spinner -->
<div class="animate-spin rounded-full h-8 w-8 border-2 border-slate-600 border-t-blue-500"></div>

<!-- Pulse Skeleton -->
<div class="animate-pulse bg-slate-700 rounded h-4 w-3/4"></div>

<!-- Progress Bar -->
<div class="w-full bg-slate-700 rounded-full h-2">
    <div class="bg-blue-600 h-2 rounded-full transition-all" style="width: 45%"></div>
</div>
```

## Layout Patterns

### Page Container

```html
<div class="min-h-screen bg-slate-900">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <!-- Content -->
    </div>
</div>
```

### Responsive Grid

```html
<!-- 1 column mobile, 2 tablet, 3 desktop -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
    <div>Item 1</div>
    <div>Item 2</div>
    <div>Item 3</div>
</div>
```

### Sidebar Layout

```html
<div class="flex min-h-screen">
    <!-- Sidebar -->
    <aside class="w-64 bg-slate-800 border-r border-slate-700 hidden lg:block">
        <!-- Sidebar content -->
    </aside>

    <!-- Main content -->
    <main class="flex-1 p-6">
        <!-- Page content -->
    </main>
</div>
```

## Animations

### Transitions

```css
/* Default transition */
.transition { transition: all 150ms ease-in-out; }

/* Slow transition */
.transition-slow { transition: all 300ms ease-in-out; }

/* Colors only */
.transition-colors { transition: color, background-color, border-color 150ms ease-in-out; }
```

### Keyframes

```css
/* Fade in */
@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

/* Slide up */
@keyframes slideUp {
    from { transform: translateY(20px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
}

/* Pulse */
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}
```

## Responsive Breakpoints

```
sm: 640px   - Small tablets
md: 768px   - Tablets
lg: 1024px  - Laptops
xl: 1280px  - Desktops
2xl: 1536px - Large screens
```

## Accessibility

### Focus States

```css
/* All interactive elements must have visible focus */
:focus-visible {
    outline: 2px solid var(--accent-primary);
    outline-offset: 2px;
}
```

### ARIA Labels

```html
<button aria-label="Close modal">
    <svg>...</svg>
</button>

<div role="alert" aria-live="polite">
    Error message here
</div>
```

### Color Contrast

- Normal text: minimum 4.5:1 ratio
- Large text: minimum 3:1 ratio
- Interactive elements: minimum 3:1 ratio

## Icons

Use Heroicons (https://heroicons.com/) or similar SVG icon library.

```html
<!-- Outline style (default) -->
<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="..."/>
</svg>

<!-- Solid style -->
<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
    <path d="..."/>
</svg>
```

## Common Patterns

### Empty State

```html
<div class="text-center py-12">
    <svg class="w-16 h-16 mx-auto text-slate-600 mb-4">...</svg>
    <h3 class="text-lg font-medium text-slate-300 mb-2">No items found</h3>
    <p class="text-slate-500 mb-4">Get started by creating your first item.</p>
    <button class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg">
        Create Item
    </button>
</div>
```

### Error State

```html
<div class="bg-red-900/20 border border-red-800 rounded-lg p-4">
    <div class="flex items-start gap-3">
        <svg class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5">...</svg>
        <div>
            <h4 class="font-medium text-red-400">Error title</h4>
            <p class="text-red-300/80 text-sm mt-1">Error description here</p>
        </div>
    </div>
</div>
```

### Toast Notifications

```html
<!-- Success toast -->
<div class="fixed bottom-4 right-4 bg-green-900 border border-green-800 rounded-lg p-4 shadow-lg flex items-center gap-3">
    <svg class="w-5 h-5 text-green-400">...</svg>
    <span class="text-green-200">Action completed successfully</span>
</div>
```

## Code Display

```html
<!-- Code block -->
<pre class="bg-slate-900 border border-slate-700 rounded-lg p-4 overflow-x-auto">
    <code class="text-sm font-mono text-slate-300">
        // Code here
    </code>
</pre>

<!-- Inline code -->
<code class="px-1.5 py-0.5 bg-slate-800 rounded text-sm font-mono text-blue-400">
    inline code
</code>
```

## Best Practices

1. **Use Tailwind utility classes** - Avoid custom CSS when possible
2. **Mobile-first** - Start with mobile styles, add responsive overrides
3. **Consistent spacing** - Use the spacing scale, don't use arbitrary values
4. **Semantic HTML** - Use appropriate HTML elements
5. **Accessible colors** - Ensure sufficient contrast
6. **Smooth transitions** - Add transitions to interactive elements
7. **Loading states** - Show loading indicators for async operations
8. **Error handling** - Display clear error messages
9. **Empty states** - Guide users when there's no content
10. **Dark mode first** - Design for dark theme, ensure light theme works

---

*This design system should be loaded before any UI work is performed.*
