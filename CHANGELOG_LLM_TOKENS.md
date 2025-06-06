# LLM Token Management Refactoring

## Overview

This document describes the comprehensive refactoring of token management across all LLM providers to fix inconsistencies and improve response quality control.

## Problem Statement

### Before Refactoring
- **Inconsistent token management**: Each provider had different approaches
- **Conflicting variables**: `MISTRAL_MAX_TOKENS` vs `RESPONSE_VERY_SHORT_MAX_TOKENS`
- **Complex logic**: min/max calculations that were error-prone
- **Mistral truncation issue**: Short responses were being cut off due to low token limits
- **OpenAI Direct limit errors**: Requesting more tokens than model supports

### Architecture Issues
- Global `RESPONSE_*_MAX_TOKENS` interfered with provider-specific limits
- Hard-coded default values in settings classes
- Inconsistent behavior between providers

## Solution

### New Architecture

#### 1. **Provider-Specific Token Configuration**
Each LLM provider now has dedicated token limits for each response size:

```env
# Azure OpenAI
AZURE_OPENAI_RESPONSE_VERY_SHORT_MAX_TOKENS=1000
AZURE_OPENAI_RESPONSE_NORMAL_MAX_TOKENS=6000  
AZURE_OPENAI_RESPONSE_COMPREHENSIVE_MAX_TOKENS=16000

# Claude
CLAUDE_RESPONSE_VERY_SHORT_MAX_TOKENS=2000
CLAUDE_RESPONSE_NORMAL_MAX_TOKENS=10000
CLAUDE_RESPONSE_COMPREHENSIVE_MAX_TOKENS=40000

# OpenAI Direct  
OPENAI_DIRECT_RESPONSE_VERY_SHORT_MAX_TOKENS=1500
OPENAI_DIRECT_RESPONSE_NORMAL_MAX_TOKENS=8000
OPENAI_DIRECT_RESPONSE_COMPREHENSIVE_MAX_TOKENS=16000

# Mistral
MISTRAL_RESPONSE_VERY_SHORT_MAX_TOKENS=1500
MISTRAL_RESPONSE_NORMAL_MAX_TOKENS=8000
MISTRAL_RESPONSE_COMPREHENSIVE_MAX_TOKENS=30000
```

#### 2. **Centralized Token Selection**
New method in `base.py`:
```python
def _get_max_tokens_for_response_size(self, provider_name: str, response_size: str) -> int:
    """Get max_tokens based on provider and response size preference."""
    provider_settings = getattr(app_settings, provider_name)
    
    if response_size == "veryShort":
        return provider_settings.response_very_short_max_tokens
    elif response_size == "comprehensive":
        return provider_settings.response_comprehensive_max_tokens
    else:  # medium/normal
        return provider_settings.response_normal_max_tokens
```

#### 3. **Settings Cleanup**
- ❌ Removed global `_ResponseSettings` class
- ❌ Removed generic `max_tokens` fields from provider settings
- ✅ Added 3 specific token fields per provider
- ✅ All settings now read from environment variables (no hard-coded defaults)

## Token Limits by Provider

### Optimized Values
- **Azure OpenAI**: Conservative limits (1K/6K/16K) - tested stable limits
- **Claude**: Generous limits (2K/10K/40K) - excellent long context handling  
- **OpenAI Direct**: Balanced (1.5K/8K/16K) - respects GPT-4o's 16384 token limit
- **Mistral**: Balanced (1.5K/8K/30K) - good performance across sizes

### Model-Specific Constraints
- **GPT-4o-2024-08-06**: Max 16384 completion tokens
- **Claude 3.5 Sonnet**: Very high limits (40K+ supported)
- **Mistral Large**: High limits (30K+ supported)

## Files Modified

### Core Changes
- `backend/settings.py`: Refactored all provider settings
- `backend/llm_providers/base.py`: New centralized token method
- `backend/llm_providers/azure_openai.py`: Updated to use new method
- `backend/llm_providers/claude.py`: Updated to use new method  
- `backend/llm_providers/openai_direct.py`: Updated to use new method
- `backend/llm_providers/mistral.py`: Updated to use new method

### Configuration
- `.env.sample`: Complete rewrite with new variables
- `.env`: Updated with production values
- Removed: `backend/settings_extended.py` (obsolete duplicate)

## Migration Guide

### For Existing Deployments
1. **Update environment variables**:
   ```bash
   # Remove old variables
   unset AZURE_OPENAI_MAX_TOKENS CLAUDE_MAX_TOKENS OPENAI_DIRECT_MAX_TOKENS MISTRAL_MAX_TOKENS
   unset RESPONSE_VERY_SHORT_MAX_TOKENS RESPONSE_COMPREHENSIVE_MAX_TOKENS
   
   # Add new provider-specific variables (see .env.sample)
   ```

2. **Copy from .env.sample**: All new variables are documented there

### Breaking Changes
- Old `*_MAX_TOKENS` variables no longer used
- Global `RESPONSE_*` variables removed
- Applications will fail to start if new variables are missing

## Benefits

### 1. **Clarity & Predictability**
- Explicit configuration per provider and response size
- No complex calculations or min/max logic
- Clear relationship between setting and behavior

### 2. **Provider Optimization**  
- Each LLM optimized for its capabilities
- Claude can use its large context window
- OpenAI Direct respects model limits
- Mistral balanced for good performance

### 3. **Maintainability**
- Consistent pattern across all providers
- Environment-driven configuration
- No hard-coded values

### 4. **Problem Resolution**
- ✅ Fixed Mistral truncation in short responses
- ✅ Fixed OpenAI Direct limit exceeded errors
- ✅ Eliminated conflicting token variables
- ✅ Consistent behavior across all LLMs

## Testing

### Verified Scenarios
- ✅ Mistral short responses: No longer truncated
- ✅ OpenAI Direct comprehensive: Respects 16K limit  
- ✅ Claude comprehensive: Uses full 40K capability
- ✅ Azure OpenAI: Stable across all sizes
- ✅ All providers: Consistent environment variable usage

## Future Considerations

### Easy Extensions
- New LLM providers follow same pattern
- Per-provider token tuning via environment variables
- Model-specific limits can be easily configured

### Monitoring
- Token usage now predictable per provider/size combination
- Easier to track and optimize costs
- Clear correlation between user choice and resource usage