let currentLang = localStorage.getItem('uk_lang') || 'en';
let translations = window.LOCALES ? window.LOCALES[currentLang] : {};

function loadLanguage(lang) {
  if (window.LOCALES && window.LOCALES[lang]) {
    translations = window.LOCALES[lang];
    currentLang = lang;
    localStorage.setItem('uk_lang', lang);
    updateDOM();
    syncAllLangSelects(lang);
  } else {
    console.warn('Translations not found for lang:', lang);
  }
}

function syncAllLangSelects(lang) {
  document.querySelectorAll('.lang-select, #authLangSelect, #sidebarLangSelect').forEach(sel => {
    sel.value = lang;
  });
}

function updateDOM() {
  document.documentElement.lang = currentLang;

  // Update inner text for all data-i18n elements
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const text = getTranslation(key);
    if (text && text !== key) {
      if (el.tagName === 'INPUT' && el.type === 'button') {
        el.value = text;
      } else {
        el.innerHTML = text;
      }
    }
  });

  // Update placeholders
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    const text = getTranslation(key);
    if (text && text !== key) {
      el.placeholder = text;
    }
  });

  // Update title attributes
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const key = el.getAttribute('data-i18n-title');
    const text = getTranslation(key);
    if (text && text !== key) {
      el.title = text;
    }
  });
}

function getTranslation(key) {
  const keys = key.split('.');
  let obj = translations;
  for (const k of keys) {
    if (obj && typeof obj === 'object' && k in obj) {
      obj = obj[k];
    } else {
      return key;
    }
  }
  return typeof obj === 'string' ? obj : key;
}

// Global translation function for use in JS
window.t = function(key) {
  return getTranslation(key);
};

window.getCurrentLang = function() {
  return currentLang;
};

// Global changeLanguage so any select can call it
window.changeLanguage = function(lang) {
  loadLanguage(lang);
};

window.loadLanguage = loadLanguage;

// Initialize language on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  const savedLang = localStorage.getItem('uk_lang') || 'en';
  // Load LOCALES-based translations
  if (window.LOCALES && window.LOCALES[savedLang]) {
    translations = window.LOCALES[savedLang];
    currentLang = savedLang;
    updateDOM();
  }
  syncAllLangSelects(savedLang);

  // Wire up ALL lang selects by class (catches any not already wired via onchange)
  document.querySelectorAll('.lang-select, #authLangSelect, #sidebarLangSelect').forEach(select => {
    select.value = savedLang;
    // Only add listener once — check for flag
    if (!select.dataset.i18nWired) {
      select.dataset.i18nWired = '1';
      select.addEventListener('change', (e) => {
        window.changeLanguage(e.target.value);
      });
    }
  });
});
