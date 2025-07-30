<script lang="ts">
	import { toast } from 'svelte-sonner';
	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import dayjs from 'dayjs';
	import relativeTime from 'dayjs/plugin/relativeTime';
	dayjs.extend(relativeTime);

	import { onMount, getContext } from 'svelte';
	const i18n = getContext('i18n');
	import { getAllUsers } from '$lib/apis/users';
	import { deleteFeedbackById, exportAllFeedbacks, getAllFeedbacks } from '$lib/apis/evaluations';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import ArrowDownTray from '$lib/components/icons/ArrowDownTray.svelte';
	import Badge from '$lib/components/common/Badge.svelte';
	import CloudArrowUp from '$lib/components/icons/CloudArrowUp.svelte';
	import Pagination from '$lib/components/common/Pagination.svelte';
	import FeedbackMenu from './FeedbackMenu.svelte';
	import FeedbackModal from './FeedbackModal.svelte';
	import EllipsisHorizontal from '$lib/components/icons/EllipsisHorizontal.svelte';

	import ChevronUp from '$lib/components/icons/ChevronUp.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import { WEBUI_BASE_URL } from '$lib/constants';

	export let feedbacks = [];
    let user_filter = '';
	
	// Ensure feedbacks is always an array
	$: safeFeedbacks = Array.isArray(feedbacks) ? feedbacks : [];
	
	let users: string[] = [];

    onMount(async () => {
        try {
            const types = await getAllUsers(localStorage.token);
            users = [...types.users.map((user: any) => user.name)];
        } catch (error) {
            console.error('Failed to load user types:', error);
        }
    });

	let page = 1;
	$: paginatedFeedbacks = sortedFeedbacks.slice((page - 1) * 10, page * 10);

	let orderBy: string = 'updated_at';
	let direction: 'asc' | 'desc' = 'desc';

	type Feedback = {
		id: string;
		data: {
			rating: number;
			model_id: string;
			sibling_model_ids: string[] | null;
			reason: string;
			comment: string;
			tags: string[];
		};
		user: {
			name: string;
			profile_image_url: string;
		};
		updated_at: number;
	};

	type ModelStats = {
		rating: number;
		won: number;
		lost: number;
	};

	function setSortKey(key: string) {
		if (orderBy === key) {
			direction = direction === 'asc' ? 'desc' : 'asc';
		} else {
			orderBy = key;
			if (key === 'user' || key === 'model_id') {
				direction = 'asc';
			} else {
				direction = 'desc';
			}
		}
		page = 1;
	}

	// Filter feedbacks based on user_filter
	$: filteredFeedbacks = user_filter 
		? safeFeedbacks.filter(feedback => {
			// Match by user name or user ID
			return feedback.user?.name === user_filter || feedback.user?.id === user_filter;
		})
		: safeFeedbacks;
	
	$: sortedFeedbacks = [...filteredFeedbacks].sort((a, b) => {
		let aVal, bVal;

		switch (orderBy) {
			case 'user':
				aVal = a.user?.name || '';
				bVal = b.user?.name || '';
				return direction === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
			case 'model_id':
				aVal = a.data.model_id || '';
				bVal = b.data.model_id || '';
				return direction === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
			case 'rating':
				aVal = a.data.details.rating;
				bVal = b.data.details.rating;
				return direction === 'asc' ? aVal - bVal : bVal - aVal;
			case 'updated_at':
				aVal = a.updated_at;
				bVal = b.updated_at;
				return direction === 'asc' ? aVal - bVal : bVal - aVal;
			default:
				return 0;
		}
	});

	let showFeedbackModal = false;
	let selectedFeedback = null;


	const openFeedbackModal = (feedback) => {
		showFeedbackModal = true;
		selectedFeedback = feedback;
	};

	const closeFeedbackModal = () => {
		showFeedbackModal = false;
		selectedFeedback = null;
	};

	//////////////////////
	//
	// CRUD operations
	//
	//////////////////////

	const deleteFeedbackHandler = async (feedbackId: string) => {
		const response = await deleteFeedbackById(localStorage.token, feedbackId).catch((err) => {
			toast.error(err);
			return null;
		});
		if (response) {
			feedbacks = feedbacks.filter((f) => f.id !== feedbackId);
		}
	};

	const exportHandler = async () => {
		const _feedbacks = await exportAllFeedbacks(localStorage.token).catch((err) => {
			toast.error(err);
			return null;
		});

		if (_feedbacks) {
			let blob = new Blob([JSON.stringify(_feedbacks)], {
				type: 'application/json'
			});
			saveAs(blob, `feedback-history-export-${Date.now()}.json`);
		}
	};
</script>

<FeedbackModal bind:show={showFeedbackModal} {selectedFeedback} onClose={closeFeedbackModal} />

<div class="mt-0.5 mb-2 gap-1 flex flex-row justify-between">
	<div class="flex md:self-center text-lg font-medium px-0.5">
		{$i18n.t('Feedback Spreadsheet')}

		<div class="flex self-center w-[1px] h-6 mx-2.5 bg-gray-50 dark:bg-gray-850" />

		<span class="text-lg font-medium text-gray-500 dark:text-gray-300">{safeFeedbacks.length}</span>
	</div>

	{#if safeFeedbacks.length > 0}
		<div>
			<Tooltip content={$i18n.t('Export')}>
				<button
					class=" p-2 rounded-xl hover:bg-gray-100 dark:bg-gray-900 dark:hover:bg-gray-850 transition font-medium text-sm flex items-center space-x-1"
					on:click={() => {
						exportHandler();
					}}
				>
					<ArrowDownTray className="size-3" />
				</button>
			</Tooltip>
		</div>
	{/if}
</div>

<div
	class="scrollbar-hidden relative whitespace-nowrap overflow-x-auto max-w-full rounded-sm pt-0.5"
>
	{#if safeFeedbacks.length === 0}
		<div class="text-center text-xs text-gray-500 dark:text-gray-400 py-1">
			{$i18n.t('No feedbacks found')}
		</div>
	{:else}
		<table
			class="w-full text-sm text-left text-gray-500 dark:text-gray-400 table-auto rounded-sm"
		>
			<thead
				class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-850 dark:text-gray-400"
			>
				<tr class="">
					<th
						scope="col"
						class="px-3 py-1 cursor-pointer select-none"
						on:click={() => setSortKey('user')}
					>
						<div class="flex gap-1.5 items-center justify-start">
                            <select 
                                bind:value={user_filter}
                                class="text-xs text-gray-700 dark:text-gray-400 bg-transparent outline-none border-none cursor-pointer w-15"
                            >
                                <option value="">{$i18n.t('USERS')}</option>
                                {#each users as userType}
                                    <option value={userType}>{userType}</option>
                                {/each}
                            </select>
						</div>
					</th>

					<th
						scope="col"
						class="px-3 py-1 cursor-pointer select-none"
						on:click={() => setSortKey('model_id')}
					>
						<div class="flex gap-1.5 items-center">
							{$i18n.t('Models')}
							{#if orderBy === 'model_id'}
								<span class="font-normal">
									{#if direction === 'asc'}
										<ChevronUp className="size-2" />
									{:else}
										<ChevronDown className="size-2" />
									{/if}
								</span>
							{:else}
								<span class="invisible">
									<ChevronUp className="size-2" />
								</span>
							{/if}
						</div>
					</th>
					<th
						scope="col"
						class="px-3 py-1 text-right cursor-pointer select-none"
						on:click={() => setSortKey('rating')}
					>
						<div class="flex gap-1.5 items-center justify-start">
							{$i18n.t('Rating')}
							{#if orderBy === 'rating'}
								<span class="font-normal">
									{#if direction === 'asc'}
										<ChevronUp className="size-2" />
									{:else}
										<ChevronDown className="size-2" />
									{/if}
								</span>
							{:else}
								<span class="invisible">
									<ChevronUp className="size-2" />
								</span>
							{/if}
						</div>
					</th>
                    <th
						scope="col"
						class="px-3 py-1 cursor-pointer select-none text-right"
					    >
						<div class="flex gap-1.5 items-center justify-start">
							{$i18n.t('Reason')}
						</div>
					</th>
                    <th
						scope="col"
						class="px-3 py-1 cursor-pointer select-none text-left"
					    >
						<div class="flex gap-1.5 items-center justify-start">
							{$i18n.t('Comment')}
						</div>
					</th>
                    <th
						scope="col"
						class="px-3 py-1 cursor-pointer select-none text-left"
					    >
						<div class="flex gap-1.5 items-center justify-start">
							{$i18n.t('Message')}
						</div>
					</th>
					<th
						scope="col"
						class="px-3 py-1 text-right cursor-pointer select-none"
						on:click={() => setSortKey('updated_at')}
					>
						<div class="flex gap-1.5 items-center justify-center">
							{$i18n.t('Updated At')}
							{#if orderBy === 'updated_at'}
								<span class="font-normal">
									{#if direction === 'asc'}
										<ChevronUp className="size-2" />
									{:else}
										<ChevronDown className="size-2" />
									{/if}
								</span>
							{:else}
								<span class="invisible">
									<ChevronUp className="size-2" />
								</span>
							{/if}
						</div>
					</th>

					<th scope="col" class="px-3 py-1 text-right cursor-pointer select-none w-8"> </th>
				</tr>
			</thead>
			<tbody class="">
				{#each paginatedFeedbacks as feedback (feedback.id)}
					<tr
						class="bg-white dark:bg-gray-900 dark:border-gray-850 text-xs cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-850/50 transition"
						on:click={() => openFeedbackModal(feedback)}
					>
						<td class="px-3 py-1 text-right font-semibold">
							<div class="flex justify-center items-center gap-2">
								<img
									src={feedback?.user?.profile_image_url ?? `${WEBUI_BASE_URL}/user.png`}
									alt=""
									class="size-5 rounded-full object-cover shrink-0"

								/>
								<span class="text-xs text-gray-600 dark:text-gray-400 truncate max-w-32">
									{feedback?.user?.name}
								</span>
							</div>
						</td>

						<td class="px-3 py-1 flex flex-col">
							<div class="flex flex-col items-start gap-0.5 h-full">
								<div class="flex flex-col h-full">
									{#if feedback.data?.sibling_model_ids}
										<div class="font-semibold text-gray-600 dark:text-gray-400 flex-1">
											{feedback.data?.model_id}
										</div>

										<Tooltip content={feedback.data.sibling_model_ids.join(', ')}>
											<div class=" text-[0.65rem] text-gray-600 dark:text-gray-400 line-clamp-1">
												{#if feedback.data.sibling_model_ids.length > 2}
													<!-- {$i18n.t('and {{COUNT}} more')} -->
													{feedback.data.sibling_model_ids.slice(0, 2).join(', ')}, {$i18n.t(
														'and {{COUNT}} more',
														{ COUNT: feedback.data.sibling_model_ids.length - 2 }
													)}
												{:else}
													{feedback.data.sibling_model_ids.join(', ')}
												{/if}
											</div>
										</Tooltip>
									{:else}
										<div
											class=" text-sm font-medium text-gray-600 dark:text-gray-400 flex-1 py-1.5"
										>
											{feedback.data?.model_id}
										</div>
									{/if}
								</div>
							</div>
						</td>
                        <td class="px-3 py-1 text-right font-medium text-gray-900 dark:text-white">
							<div class="flex items-center justify-start">
								<span>{feedback.data.details.rating.toString()}</span>
							</div>
						</td>
                        <td class="px-3 py-1 text-left font-medium text-gray-900 dark:text-white">
							<div class="flex gap-1.5 items-center justify-start">
								<span>
									{feedback.data.reason.slice(0, 100)}
								</span>
							</div>
						</td>
                        <td class="px-3 py-1 text-left font-medium text-gray-900 dark:text-white">
							<div class="flex gap-1.5 items-center justify-start">
								<span>
									{feedback.data.comment.slice(0, 100)}
								</span>
							</div>
						</td>
                        <td class="px-3 py-1 text-left font-medium text-gray-900 dark:text-white">
							<div class="flex gap-1.5 items-center justify-start">
									<span>
                                     {feedback?.message?.slice(0, 100) || ''}
								</span>
							</div>
						</td>
						<td class="px-11 py-1 text-right font-medium">
                            <div class="flex items-center justify-end">
								{dayjs(feedback.updated_at * 1000).fromNow()}
							</div>
						</td>
						<td class="px-3 py-1 text-right font-semibold w-8" on:click={(e) => e.stopPropagation()}>
							<FeedbackMenu
								on:delete={(e) => {
									deleteFeedbackHandler(feedback.id);
								}}
							>
								<button
									class="w-6 h-6 flex items-center justify-center text-sm dark:text-gray-300 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 rounded"
								>
									<EllipsisHorizontal />
								</button>
							</FeedbackMenu>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}
</div>

	{#if safeFeedbacks.length > 10}
	<Pagination bind:page count={safeFeedbacks.length} perPage={10} />
{/if}
