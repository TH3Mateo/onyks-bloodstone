<script setup>
    import { ref, watch, computed } from 'vue';
    import { elementDocument } from '@/utils/api.js';

    const props = defineProps(['elementUuid', 'docsCount', 'disabled'])
    const emit = defineEmits(['change'])

    // The backend owns the count; keep a local copy so the tiles update straight after
    // an upload or a delete without re-fetching the whole element.
    const count = ref(props.docsCount || 0)
    watch(() => props.docsCount, (value) => { count.value = value || 0 })

    const uploader = ref(null)
    const busy = ref(false)
    const error = ref('')

    const documents = computed(() => Array.from({ length: count.value }, (_, i) => i + 1))

    const apply = (response) =>
    {
        if (response?.status == 200)
        {
            count.value = response.data.docsCount
            emit('change', count.value)
            return true
        }
        error.value = response?.response?.data?.detail || 'Operation failed.'
        return false
    }

    const add = async () =>
    {
        const file = uploader.value?.files?.[0]
        if (!file)
        {
            error.value = 'Pick a PDF file first.'
            return
        }

        error.value = ''
        busy.value = true
        const response = await elementDocument.upload(props.elementUuid, file)
        busy.value = false

        if (apply(response))
        {
            uploader.value.reset()
        }
    }

    const remove = async (index) =>
    {
        error.value = ''
        busy.value = true
        const response = await elementDocument.delete(props.elementUuid, index)
        busy.value = false
        apply(response)
    }
</script>

<template>
    <onyks-container gap="s" padding="" type="stack">

        <onyks-container v-if="count > 0" gap="s" type="grid" cols="2" padding="">
            <onyks-container v-for="index in documents" :key="index" gap="s" type="group" align="center" padding="">
                <onyks-button size="s" background="blue" @click="elementDocument.open(props.elementUuid, index)">
                    Document {{ index }}
                </onyks-button>
                <onyks-button v-if="!props.disabled" size="s" background="red" :disabled="busy" @click="remove(index)">
                    Delete
                </onyks-button>
            </onyks-container>
        </onyks-container>

        <onyks-text v-else size="m">No additional documents.</onyks-text>

        <template v-if="!props.disabled">
            <onyks-file-upload ref="uploader" accept=".pdf" message="Drag a PDF or click to add it"></onyks-file-upload>
            <onyks-button background="green" :disabled="busy" @click="add">Add document</onyks-button>
        </template>

        <onyks-alert v-if="error" type="warning">{{ error }}</onyks-alert>

    </onyks-container>
</template>

<style scoped>
    onyks-file-upload
    {
        width: 100%;
    }

    onyks-button
    {
        width: auto;
        flex: 1;
    }
</style>
