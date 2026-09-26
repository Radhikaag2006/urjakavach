let currentLang = localStorage.getItem('uk_lang') || 'en';
let translations = window.LOCALES ? window.LOCALES[currentLang] : {};

function loadLanguage(lang) {
  if (window.LOCALES && window.LOCALES[lang]) {
    translations = window.LOCALES[lang];
    currentLang = lang;
    localStorage.setItem('uk_lang', lang);
    updateDOM();
  } else {
    console.error('Translations not found for', lang);
  }
}

function updateDOM() {
  document.documentElement.lang = currentLang;
  
  // Update inner text
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
}

function getTranslation(key) {
  const keys = key.split('.');
  let obj = translations;
  for (const k of keys) {
    if (obj && obj[k]) {
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

// Initialize language on load
document.addEventListener("DOMContentLoaded", () => {
  loadLanguage(currentLang);
  
  // Update language select if it exists
  const langSelects = document.querySelectorAll('.lang-select');
  langSelects.forEach(select => {
    select.value = currentLang;
    select.addEventListener('change', (e) => {
      changeLanguage(e.target.value);
    });
  });
});

window.changeLanguage = function(lang) {
  loadLanguage(lang);
  const langSelects = document.querySelectorAll('.lang-select');
  langSelects.forEach(select => {
    select.value = lang;
  });
};
