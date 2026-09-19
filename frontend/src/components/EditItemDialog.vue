<script setup>
    import { ref } from 'vue';
    import { defineExpose } from 'vue';

    const emit = defineEmits(['success'])
    const props = defineProps(['subject', 'action'])

    const name = ref('')
    const currentName = ref('')
    const id = ref(0)

    const error = ref('')
    const dialog = ref(null)
    
    const open = (a, b) => 
    {
        name.value = a
        id.value = b
        currentName.value = a
        error.value = ''
        dialog.value.open = true
    }

    const close = () =>
    {
        dialog.value.open = false
    }

    const action = async () =>
    {
        let data = await props.action(id.value, {name: name.value.trim()})
        console.log(data)
        if(data.status == 200)
        {
            dialog.value.open = false
            emit('success')
        }
        else
        {
            error.value = data.response.data.detail
        }
    }

    defineExpose({
        open,
        close
    });
</script>

<template>

    <onyks-dialog :title="`Editing a ${props.subject}`" corner-close bottom-buttons modal ref="dialog">
        <onyks-container type="stack" padding="" gap="l">
            <onyks-text size="m">You are editing: {{ currentName }}.</onyks-text>
            <onyks-text>Enter a new name of the {{ props.subject }} below:</onyks-text>
            <onyks-textfield :placeholder="`New name of the ${props.subject}`" v-model="name" @input="error = ''"></onyks-textfield>
            <onyks-text :class="error === '' ? 'error-invisible' : ''">{{ error }}</onyks-text>
        </onyks-container>
        <onyks-button background="green" slot="footer" @click="action" size="m">OK</onyks-button>
        <onyks-button background="red" slot="footer" @click="dialog.open = false">Close</onyks-button>
    </onyks-dialog>

</template>

<style lang="css" scoped>
    onyks-textfield
    {
        width: 100%;
    }

    .error-invisible
    {
        visibility: hidden;
    }

    onyks-dialog
    {
        position: fixed;
    }
</style>