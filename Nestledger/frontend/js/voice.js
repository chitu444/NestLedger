/* NestLedger voice navigation module.
 * Browser-native SpeechRecognition + SpeechSynthesis only -- no paid API.
 * Depends on globals defined in app.js: state, go(page), api(path), toast(msg).
 * Depends on window.i18n for the active language and speech locale.
 */
(function (global) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  // Clean command -> action mapping instead of long if/else chains.
  // Each command lists recognizable phrases per language; matching is done
  // by checking whether the transcript *contains* one of these phrases,
  // so minor filler words around the phrase don't break recognition.
  const commands = [
    {
      id: 'dashboard',
      phrases: {
        en: ['go to dashboard', 'open dashboard', 'dashboard'],
        ta: ['டாஷ்போர்டுக்கு செல்', 'டாஷ்போர்டு'],
        ml: ['ഡാഷ്ബോർഡിലേക്ക് പോകുക', 'ഡാഷ്ബോർഡ്'],
        kn: ['ಡ್ಯಾಶ್‌ಬೋರ್ಡ್‌ಗೆ ಹೋಗಿ', 'ಡ್ಯಾಶ್‌ಬೋರ್ಡ್'],
        te: ['డాష్‌బోర్డ్‌కు వెళ్ళు', 'డాష్‌బోర్డ్'],
        hi: ['डैशबोर्ड पर जाओ', 'डैशबोर्ड खोलो', 'डैशबोर्ड'],
      },
      run: () => go('dashboard'),
    },
    {
      id: 'payments',
      phrases: {
        en: ['go to payments', 'open payments', 'payments'],
        ta: ['கட்டணங்களுக்கு செல்', 'கட்டணங்கள்'],
        ml: ['പേയ്‌മെന്റുകളിലേക്ക് പോകുക', 'പേയ്‌മെന്റുകൾ'],
        kn: ['ಪಾವತಿಗಳಿಗೆ ಹೋಗಿ', 'ಪಾವತಿಗಳು'],
        te: ['చెల్లింపులకు వెళ్ళు', 'చెల్లింపులు'],
        hi: ['भुगतान पर जाओ', 'भुगतान खोलो', 'भुगतान'],
      },
      run: () => go('payments'),
    },
    {
      id: 'complaints',
      phrases: {
        en: ['show complaints', 'go to complaints', 'raise complaint', 'complaints'],
        ta: ['புகார்களைக் காட்டு', 'புகார் அளி', 'புகார்கள்'],
        ml: ['പരാതികൾ കാണിക്കുക', 'പരാതി നൽകുക', 'പരാതികൾ'],
        kn: ['ದೂರುಗಳನ್ನು ತೋರಿಸಿ', 'ದೂರು ನೀಡಿ', 'ದೂರುಗಳು'],
        te: ['ఫిర్యాదులు చూపించు', 'ఫిర్యాదు చేయి', 'ఫిర్యాదులు'],
        hi: ['शिकायतें दिखाओ', 'शिकायत दर्ज करो', 'शिकायतें'],
      },
      run: () => go('complaints'),
    },
    {
      id: 'notices',
      phrases: {
        en: ['show notices', 'go to notices', 'notices'],
        ta: ['அறிவிப்புகளைக் காட்டு', 'அறிவிப்புகள்'],
        ml: ['അറിയിപ്പുകൾ കാണിക്കുക', 'അറിയിപ്പുകൾ'],
        kn: ['ಸೂಚನೆಗಳನ್ನು ತೋರಿಸಿ', 'ಸೂಚನೆಗಳು'],
        te: ['నోటీసులు చూపించు', 'నోటీసులు'],
        hi: ['सूचनाएं दिखाओ', 'सूचनाएं'],
      },
      run: () => go('notices'),
    },
    {
      id: 'workorders',
      phrases: {
        en: ['go to maintenance', 'job board', 'work orders', 'maintenance'],
        ta: ['பராமரிப்புக்கு செல்', 'பராமரிப்பு'],
        ml: ['അറ്റകുറ്റപ്പണിയിലേക്ക് പോകുക', 'അറ്റകുറ്റപ്പണി'],
        kn: ['ನಿರ್ವಹಣೆಗೆ ಹೋಗಿ', 'ನಿರ್ವಹಣೆ'],
        te: ['నిర్వహణకు వెళ్ళు', 'నిర్వహణ'],
        hi: ['रखरखाव पर जाओ', 'रखरखाव'],
      },
      run: () => go('workorders'),
    },
    {
      id: 'receipts',
      phrases: {
        en: ['go to receipts', 'open receipts', 'receipts'],
        ta: ['ரசீதுகளுக்கு செல்', 'ரசீதுகள்'],
        ml: ['രസീതുകളിലേക്ക് പോകുക', 'രസീതുകൾ'],
        kn: ['ರಸೀದಿಗಳಿಗೆ ಹೋಗಿ', 'ರಸೀದಿಗಳು'],
        te: ['రసీదులకు వెళ్ళు', 'రసీదులు'],
        hi: ['रसीदों पर जाओ', 'रसीदें'],
      },
      run: () => go('receipts'),
    },
    {
      id: 'profile',
      phrases: {
        en: ['go to profile', 'open profile', 'my profile', 'profile'],
        ta: ['சுயவிவரத்திற்கு செல்', 'சுயவிவரம்'],
        ml: ['പ്രൊഫൈലിലേക്ക് പോകുക', 'പ്രൊഫൈൽ'],
        kn: ['ಪ್ರೊಫೈಲ್‌ಗೆ ಹೋಗಿ', 'ಪ್ರೊಫೈಲ್'],
        te: ['ప్రొఫైల్‌కు వెళ్ళు', 'ప్రొఫైల్'],
        hi: ['प्रोफ़ाइल पर जाओ', 'प्रोफ़ाइल'],
      },
      run: () => go('profile'),
    },
    {
      id: 'logout',
      phrases: {
        en: ['log out', 'logout', 'sign out'],
        ta: ['வெளியேறு'],
        ml: ['ലോഗ് ഔട്ട്'],
        kn: ['ಲಾಗ್ ಔಟ್'],
        te: ['లాగ్ అవుట్'],
        hi: ['लॉग आउट', 'साइन आउट'],
      },
      run: () => logout(),
    },
    {
      id: 'read_dues',
      phrases: {
        en: ['read my dues', 'what do i owe', 'my dues'],
        ta: ['என் நிலுவைத் தொகையைப் படி', 'நிலுவைத் தொகை'],
        ml: ['എന്റെ കുടിശ്ശിക വായിക്കുക', 'കുടിശ്ശിക'],
        kn: ['ನನ್ನ ಬಾಕಿ ಓದಿ', 'ಬಾಕಿ'],
        te: ['నా బకాయిలు చదవండి', 'బకాయిలు'],
        hi: ['मेरा बकाया पढ़ो', 'बकाया'],
      },
      run: async () => {
        try {
          const d = await api('/dashboard');
          const due = d.due || 0;
          speak(`${window.i18n.t('pending')}: ₹${due}`);
        } catch (e) {
          speak(window.i18n.t('voiceUnsupported'));
        }
      },
    },
    {
      id: 'help',
      phrases: {
        en: ['help'], ta: ['உதவி'], ml: ['സഹായം'], kn: ['ಸಹಾಯ'], te: ['సహాయం'], hi: ['मदद'],
      },
      run: () => {
        const msg = 'Try saying: dashboard, payments, receipts, maintenance, complaints, notices, profile, read my dues, or log out.';
        toast(msg);
        speak(msg);
      },
    },
  ];

  // Human-readable explanations for SpeechRecognition error codes.
  // Falls back to English if the active language isn't covered.
  const errorMessages = {
    'not-allowed': {
      en: 'Microphone access is blocked. Please allow microphone permission for this site and try again.',
      hi: 'माइक्रोफ़ोन की अनुमति नहीं मिली। कृपया इस साइट के लिए माइक्रोफ़ोन की अनुमति दें और फिर से प्रयास करें।',
    },
    'permission-denied': {
      en: 'Microphone access is blocked. Please allow microphone permission for this site and try again.',
    },
    'service-not-allowed': {
      en: 'Microphone access is blocked. Please allow microphone permission for this site and try again.',
    },
    'no-speech': {
      en: "I didn't hear anything. Tap the mic and try again.",
      hi: 'कुछ सुनाई नहीं दिया। माइक पर टैप करें और फिर से बोलें।',
    },
    'audio-capture': {
      en: 'No microphone was found on this device.',
      hi: 'इस डिवाइस पर कोई माइक्रोफ़ोन नहीं मिला।',
    },
    network: {
      en: 'Voice recognition needs an internet connection. Please check your network and try again.',
      hi: 'आवाज़ पहचानने के लिए इंटरनेट कनेक्शन चाहिए। कृपया अपना नेटवर्क जांचें।',
    },
    aborted: null, // user or system cancelled; no need to alarm them
  };

  function errorMessageFor(code) {
    const lang = window.i18n.getLanguage();
    const entry = errorMessages[code];
    if (entry === null) return null; // intentionally silent
    if (entry) return entry[lang] || entry.en;
    return `${window.i18n.t('voiceUnsupported')} (${code})`;
  }

  let recognition = null;
  let listening = false;

  function speak(text) {
    if (!window.speechSynthesis) return;
    const lang = window.i18n.getLanguage();
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = window.i18n.SPEECH_LOCALE[lang] || 'en-IN';
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utter);
  }

  function matchCommand(transcript) {
    const lang = window.i18n.getLanguage();
    const text = transcript.trim().toLowerCase();
    for (const cmd of commands) {
      const phrases = cmd.phrases[lang] || cmd.phrases.en;
      if (phrases.some((p) => text.includes(p.toLowerCase()))) return cmd;
    }
    return null;
  }

  function ensureRecognition() {
    if (!SR) return null;
    if (recognition) return recognition;
    recognition = new SR();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      const cmd = matchCommand(transcript);
      if (cmd) {
        cmd.run();
      } else {
        const msg = `"${transcript}" — try: dashboard, payments, complaints, or say "help".`;
        toast(msg);
        speak(window.i18n.t('noData'));
      }
    };
    recognition.onerror = (event) => {
      listening = false;
      updateMicUI();
      const msg = errorMessageFor(event.error);
      if (msg) toast(msg); // null (e.g. "aborted") stays silent on purpose
    };
    recognition.onend = () => {
      listening = false;
      updateMicUI();
    };
    return recognition;
  }

  function updateMicUI() {
    const btn = document.getElementById('voiceMicBtn');
    if (btn) btn.classList.toggle('listening', listening);
  }

  function startListening() {
    const r = ensureRecognition();
    if (!r) {
      toast(window.i18n.t('voiceUnsupported'));
      return;
    }
    if (listening) return;
    r.lang = window.i18n.SPEECH_LOCALE[window.i18n.getLanguage()] || 'en-IN';
    try {
      r.start();
      listening = true;
      updateMicUI();
      toast(window.i18n.t('voiceListening'));
    } catch (e) {
      // InvalidStateError fires if recognition is already running -- that's
      // harmless and can be ignored. Anything else means it never started,
      // so the user needs to know instead of the button doing nothing.
      if (e && e.name !== 'InvalidStateError') {
        toast(errorMessageFor('not-allowed'));
      }
    }
  }

  function mountMicButton() {
    if (document.getElementById('voiceMicBtn')) return;
    const btn = document.createElement('button');
    btn.id = 'voiceMicBtn';
    btn.className = 'voice-mic';
    btn.type = 'button';
    btn.setAttribute('aria-label', 'Voice navigation');
    btn.innerHTML = `<span class="voice-mic-icon">🎤</span><span class="voice-mic-label">${window.i18n.t('voiceTapToSpeak')}</span>`;
    btn.onclick = startListening;
    document.body.appendChild(btn);
  }

  function refreshLabel() {
    const btn = document.getElementById('voiceMicBtn');
    if (btn) {
      const label = btn.querySelector('.voice-mic-label');
      if (label) label.textContent = window.i18n.t('voiceTapToSpeak');
    }
  }

  function unmountMicButton() {
    if (recognition) {
      try { recognition.abort(); } catch (e) {}
    }
    listening = false;
    const btn = document.getElementById('voiceMicBtn');
    if (btn) btn.remove();
  }

  global.NLVoice = { mountMicButton, unmountMicButton, refreshLabel, supported: !!SR };
})(window);
