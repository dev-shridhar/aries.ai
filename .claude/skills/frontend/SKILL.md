# Skill: Frontend Standards

Instructions for development in `/frontend`.

## Focus Areas
1. **Premium Design**: Use smooth transitions and modern color palettes. Avoid default browser styles.
2. **Component Structure**: Functional React components. Use hooks (e.g., `useAries`, `useWebSocket`) for logic.
3. **State Management**: Keep local state in components; use Context or specialized hooks for global agent state.
4. **Resiliency**: Handle WebSocket disconnections gracefully with auto-reconnect logic.

## Workflow
1. Run `npm run dev` in `/frontend`.
2. Use `eslint` to maintain code quality.
3. Verify that all interactive elements have unique IDs for automated browser testing.
