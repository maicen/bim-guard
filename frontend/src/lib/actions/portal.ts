/** Moves a node to <body> so overflow/clipping containers (tables, scroll panes) can't clip it. */
export function portal(node: HTMLElement) {
  document.body.appendChild(node);
  return {
    destroy() {
      node.remove();
    },
  };
}
