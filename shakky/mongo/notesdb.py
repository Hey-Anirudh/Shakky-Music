from shakky.utils.mongo import db

notes_collection = db["notes"]

async def SaveNote(chat_id, note_name, content, text, data_type):
    new_note = {
        'note_name': note_name,
        'content': content,
        'text': text,
        'data_type': data_type
    }

    result = await notes_collection.update_one(
        {
            'chat_id': chat_id,
            'notes.note_name': note_name
        },
        {
            '$set': {
                'notes.$': new_note
            }
        }
    )

    if result.matched_count == 0:
        await notes_collection.update_one(
            {
                'chat_id': chat_id
            },
            {
                '$push': {
                    'notes': new_note
                }
            },
            upsert=True
        )

async def GetNote(chat_id, note_name):
    GetNoteData = await notes_collection.find_one(
        {
            'chat_id': chat_id,
            'notes.note_name': note_name
        },
        {
            'notes.$': 1
        }
    )

    if GetNoteData and 'notes' in GetNoteData:
        note = GetNoteData['notes'][0]
        content = note.get('content')
        text = note.get('text')
        data_type = note.get('data_type')
        return content, text, data_type
    else:
        return None

async def isNoteExist(chat_id, note_name) -> bool:
    GetNoteData = await notes_collection.find_one(
        {
            'chat_id': chat_id,
            'notes.note_name': note_name
        }
    )
    return GetNoteData is not None

async def NoteList(chat_id) -> list:
    NotesNamesList = []
    GetNoteData = await notes_collection.find_one(
        {
            'chat_id': chat_id
        },
        {
            'notes.note_name': 1,
            'notes.text': 1
        }
    )
    if GetNoteData and 'notes' in GetNoteData:
        for note in GetNoteData['notes']:
            NoteText = note.get('text', '')
            NoteName = note['note_name']
            if '{admin}' in NoteText:
                NoteName += ' __{admin}__'
            NotesNamesList.append(NoteName)
    return NotesNamesList

async def ClearNote(chat_id, note_name):
    await notes_collection.update_one(
        {
            'chat_id': chat_id
        },
        {
            '$pull': {
                'notes': {
                    'note_name': note_name
                }
            }
        }
    )

async def is_pnote_on(chat_id) -> bool:
    GetNoteData = await notes_collection.find_one(
        {
            'chat_id': chat_id
        },
        {
            'private_note': 1
        }
    )
    if GetNoteData:
        return GetNoteData.get('private_note', False)
    else:
        return False

async def ClearAllNotes(chat_id):
    await notes_collection.update_one(
        {
            'chat_id': chat_id
        },
        {
            '$set': {
                'notes': []
            }
        }
    )

async def set_private_note(chat_id, private_note):
    await notes_collection.update_one(
        {
            'chat_id': chat_id
        },
        {
            '$set': {
                'private_note': private_note
            }
        },
        upsert=True
    )
