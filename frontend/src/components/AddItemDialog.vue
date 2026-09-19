<script setup>
    import { ref } from 'vue'

    const props = defineProps(['subject', 'action'])
    const emit = defineEmits(['success'])
    
    const dialog = ref(null)
    const error = ref('')
    const name = ref('')

    const open = () => 
    {
        name.value = ''
        error.value = ''
        dialog.value.open = true
    }

    const close = () =>
    {
        dialog.value.open = false
    }

    const action = async () =>
    {
        let data = await props.action({name: name.value.trim()})
       
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
    <onyks-dialog :title="`Adding a ${props.subject}`" corner-close bottom-buttons modal ref="dialog">
        <onyks-container type="stack" padding="" gap="l">
            <onyks-text>Enter the name of a new {{ props.subject }} below:</onyks-text>
            <onyks-textfield :placeholder="`Name of a new ${props.subject}`" v-model="name" @input="error = ''"></onyks-textfield>
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