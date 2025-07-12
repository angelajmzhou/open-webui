<script lang="ts">
    // @ts-nocheck
    import { onMount, getContext } from 'svelte';
    import { toast } from 'svelte-sonner';
    import { dirHandle } from '$lib/stores';
    const i18n = getContext('i18n');

    let customFilename = '';
    export let saveHandler: Function;

    const setFilePath = async () => {
    try {
        const handle = await window.showDirectoryPicker();
        dirHandle.set(handle);


        toast.success('File path set');
        console.log('Chosen file handle:', handle);
    } catch (err) {
        if (err.name !== 'AbortError') {
            console.error('Failed to pick save path:', err);
            toast.error('Failed to set file path');
        }
    }
};

    onMount(() => {
        // Any init logic
    });
</script>


<form
    class="flex flex-col h-full justify-between space-y-3 text-sm"
    on:submit|preventDefault={async () => {
        saveHandler();
    }}
>
    <div class="flex justify-end pt-3 text-sm font-medium">
        <button
            class="text-xs px-3 py-1.5 bg-gray-50 hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800 transition rounded-lg font-medium"
            type="button"
            on:click={setFilePath}
        >
            {$i18n?.t('Set export location') || 'Set Export Location'}
        </button>
    </div>
</form>
