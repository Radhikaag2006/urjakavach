function formatDeliverableMarkdown(text, msgId) {
  if (!text) return '';
  let html = text
    .replace(/^### (.*$)/gim, '<h4>$1</h4>')
    .replace(/^## (.*$)/gim, '<h3>$1</h3>')
    .replace(/^# (.*$)/gim, '<h2>$1</h2>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^\s*[-*•]\s+(.*$)/gim, '<li>$1</li>')
    .replace(/^\s*\d+\.\s+(.*$)/gim, '<li>$1</li>');

  html = html.replace(/((?:<li>.*<\/li>\s*)+)/g, '<ul>$1</ul>');

  const parts = html.split(/(<div class=\"chat-sandbox-box\">[\s\S]*?<\/div>\s*<\/div>)/g);
  return parts.map((part, i) => {
    if (i % 2 === 1) return part;
    return part.split(/\n\n+/).map(p => p.trim() ? `<p>${p.replace(/\n/g, '<br>')}</p>` : '').join('');
  }).join('');
}
console.log(formatDeliverableMarkdown('Namaste! Main UrjaKavach hoon. Aap kya chahte hain?'));
