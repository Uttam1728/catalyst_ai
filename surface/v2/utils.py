from utils.common import MessageTransformer
from utils.connection_handler import gandalf_read_connection_handler
from wrapper.ai_models import ModelRegistry
from wrapper.dao import LLMModelConfigDAO


async def transform_messages_v2(data, model_name):
    for message in data:
        role = message.get('role')
        content = ""

        prompt_details = message.get('prompt_details', {})

        if 'references' in prompt_details:
            reference_content = MessageTransformer.create_content_from_reference(prompt_details['references'])
            if 'enhancedFileContext' in prompt_details:
                reference_content += "Enhanced File Context For More Reference\n"
                reference_content += prompt_details['enhancedFileContext']
            new_content = [{"type": "text", "text": reference_content}]
        else:
            new_content = [{"type": "text", "text": content.strip()}]

        model_llm = ModelRegistry.get_model(model_name)

        if 'references' in prompt_details:
            if model_llm.config.accept_image and 'image' in prompt_details['references'] or 'images' in prompt_details[
                'references']:
                new_content = await transform_image_messages_v2(prompt_details, model_name, new_content)

        message.clear()
        message['role'] = role
        message['content'] = new_content

    return data


async def transform_image_messages_v2(prompt_details, model_name, new_content):
    images = prompt_details.get('references', {}).get('images', [])[:4]
    async with gandalf_read_connection_handler() as connection_handler:
        model_details = await LLMModelConfigDAO(connection_handler.session).get_config_from_model_name(model_name)

    if not model_details.accept_image:
        return new_content
    for image_url in images:
        if not image_url:
            continue

        if "openai" in model_name or "gpt" in model_name or "o1" in model_name:
            new_content.append({
                "type": "image_url",
                "image_url": {
                    "url": image_url,
                },
            })
        elif "claude" in model_name:
            parts = image_url.split(',', 1)
            media_type = "image/" + parts[0].split(';')[0].split('/')[1] if len(parts) > 1 else 'unknown'
            base64_data = parts[1] if len(parts) > 1 else ''

            new_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64_data,
                }
            })

    return new_content
