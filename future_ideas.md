# future_ideas.md
- Plugin-based language architecture
- Add new language via config/YAML only
- No code changes needed for new language
- Languages: Hindi, Tamil, Telugu, Kannada...
```

**The design is simple:**
```
languages/
├── english.yaml
├── hindi.yaml
├── hinglish.yaml
└── tamil.yaml  ← just add file, done!
```

Tell Claude Code tomorrow:
```
"Make language detection pluggable 
via YAML config files"