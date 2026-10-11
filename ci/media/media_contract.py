"""Provider-neutral source-separated contract; does not download media or call AI."""
SOURCE_TYPES={'telegram_photo','telegram_voice','telegram_audio','telegram_document','telegram_video','instagram_reel'}

def normalize_worker_result(result, source_ref):
    kind=result['source_type']
    if kind not in SOURCE_TYPES:raise ValueError('unsupported_media_source')
    speech=result.get('speech')
    visual=result.get('visual')
    ocr=result.get('on_screen_text')
    errors=list(result.get('errors',[]))
    missing=[]
    if kind in {'telegram_voice','telegram_audio','telegram_video','instagram_reel'}:
        if not speech or not speech.get('engine') or not speech.get('text','').strip():missing.append('AUDIO/SPEECH')
    if kind in {'telegram_photo','telegram_video','instagram_reel'}:
        if not ocr or not ocr.get('engine') or ocr.get('warning'):missing.append('ON_SCREEN_TEXT')
        if not visual or visual.get('status')!='ok':missing.append('VISUAL')
    if kind=='telegram_document' and not result.get('document_text','').strip():missing.append('DOCUMENT_TEXT')
    return {'source_ref':source_ref,'source_type':kind,'status':'EXTRACTED' if not missing and not errors else 'WAITING_MEDIA',
            'AUDIO/SPEECH':speech,'ON_SCREEN_TEXT':ocr,'VISUAL':visual,
            'CAPTION':result.get('caption',''),'DOCUMENT_TEXT':result.get('document_text'),
            'AI_ANALYSIS':None,'missing':missing,'errors':errors}
